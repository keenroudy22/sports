/* Kook'n redesign prototype (Hybrid A + B, casino felt).
   Plain-English best bets on Today, one sortable Research board, honest Record.
   Every number comes from the build's payloads; this file lays them out and does small, tested math.
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
  const researchPrice = row => {
    const g = row.grade || row;
    const needs = isNum(g.needs) ? g.needs : breakEven(row.odds);
    const chance = g.calibrated === false ? null : g.chance;
    if (!isNum(chance) || !isNum(needs)) return 'No price check available';
    const clear = row.clearsPrice === true || (g.calibrated === true && ['lean', 'strong'].includes(g.view || g.tier) && !g.thin && !g.limited && !g.unproven && g.edge > 0);
    return `We give it ${pctText(chance)}. This price needs ${pctText(needs)} to win often enough. ${clear ? 'The chance is high enough for our price check.' : 'Our chance is not high enough at this price.'}`;
  };
  const matchupSignals = (row, trend, defense) => Number(row.clearsPrice === true) + Number(Boolean(trend)) + Number(Boolean(defense));
  const priceMatch = (row, lines, now = Date.now()) => (lines || []).find(line => officialKey(line) === officialKey(row) && Number(line.line) === Number(row.line)
    && bookLabel(line.book) === bookLabel(row.book) && Number(line.odds) === Number(row.odds) && line.state === 'open'
    && Date.parse(line.observedAt) <= now && now - Date.parse(line.observedAt) <= 4 * 3600000) || null;
  const averageGap = (projection, values) => {
    if (!isNum(projection) || !values.length || !values.every(isNum)) return '';
    const average = values.reduce((a, b) => a + b, 0) / values.length;
    return average > 0 && Math.abs(projection - average) / average > .3 ? `Our average is ${round1(projection)}; his last ${values.length} games averaged ${round1(average)}. Wide range, low certainty.` : '';
  };
  const goodTo = pick => isNum(pick.cutoffOdds) && isNum(pick.cutoffLine) ? `Still a bet down to ${oddsText(pick.cutoffOdds)} at ${pick.cutoffLine}` : '';
  /* A row the A-22/A-23 checks hold (role, quarterback change or price): never a live quote, never graded. */
  const heldRow = r => Boolean(r && (r.roleSuspect || r.priceSuspect || r.roleHold));
  /* The hold on a player market from its board rows (any book, either side), as build_site.ticket_hold words it. */
  const holdOf = rows => {
    const held = (rows || []).filter(heldRow);
    if (!held.length) return null;
    const work = held.find(r => r.roleHold === 'workload' && (r.recentFull || []).length === 3);
    if (work) return { kind: 'workload', recentFull: work.recentFull, volume: work.recentVolume };
    if (held.some(r => r.roleHold === 'qb')) return { kind: 'qb' };
    return { kind: held.some(r => r.roleSuspect || r.roleHold) ? 'role' : 'price' };
  };
  const SAME_VOLUME = { recYds: 'targets', rec: 'targets', rushYds: 'carries', car: 'carries', passYds: 'att', att: 'att', cmp: 'att' };
  /* A published play's hold: the build's (today.json and the hero carry it), else its market's board rows. */
  const pickHold = (pick, rows) => {
    if (!pick || pick.result || !pick.athleteId) return null;
    if (pick.held) return pick.held;
    const key = C ? C.marketKey(pick) : pick.market;
    const hold = holdOf((rows || []).filter(r => r.gameId === pick.gameId && String(r.athleteId) === String(pick.athleteId)
      && ((C ? C.marketKey(r) : r.stat) === key || (SAME_VOLUME[key] && SAME_VOLUME[C ? C.marketKey(r) : r.stat] === SAME_VOLUME[key] && r.roleSuspect))));
    return hold && (pick.delivery?.discordAt || pick.delivery?.xAt) ? { ...hold, afterPosting: true } : hold;
  };
  const VOLUME_WORD = { att: 'pass attempts', targets: 'targets', carries: 'carries' };
  const listWords = xs => xs.length > 1 ? `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}` : String(xs[0] || '');
  /* The plain held sentence (NOTES 4.4). Only real recent full-game volumes are quoted; never the held projection. */
  const heldWords = hold => !hold ? ''
    : hold.kind === 'workload' && (hold.recentFull || []).length === 3 ? `My workload number for him is far below his last three full games (${listWords(hold.recentFull)} ${VOLUME_WORD[hold.volume] || ''}), so I'm checking his role first.`.replace(' )', ')')
      : hold.kind === 'qb' ? "His team's quarterback picture changed, so I'm checking his role first."
        : hold.kind === 'price' ? "That price failed my sanity check, so I'm checking it first."
          : "My workload number for him doesn't match his recent full games, so I'm checking his role first.";
  /* One short line for the Today ticket. */
  const HELD_WORDS = /\bproject|\bchance\b|\bedge\b|\bmodel\b|\bfair\b|\d%|^Role: /i;
  const heldShort = hold => hold.kind === 'price' ? 'Under review · checking that price first.' : 'Under review · checking his role first.';
  const afterPostingWords = hold => hold.kind === 'qb' ? "His team's quarterback picture changed since I posted, so I'm checking his role."
    : hold.kind === 'price' ? 'That price moved further than I like since I posted.'
      : 'His recent workload looks lighter than my number assumed since I posted.';
  const heldQuote = (pick, rows, now = Date.now()) => {
    const same = [pick.quote, ...(rows || []).filter(r => officialKey(r) === officialKey(pick) && bookLabel(r.book) === bookLabel(pick.book) && r.state === 'open')]
      .filter(r => r && isNum(r.odds) && Date.parse(r.observedAt) <= now && now - Date.parse(r.observedAt) <= 4 * 3600000)
      .sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt));
    return same[0] || null;
  };
  /* The latest fresh same-book quote for a play: the build's own (pick.quote, on the first paint and the full card
     alike), or a current board row for the same market and side. A held market has none. */
  const latestPickQuote = (pick, rows, now = Date.now()) => {
    if (Date.parse(pick.kickoff) <= now || pick.held) return null;
    const own = pick.quote && isNum(pick.quote.odds) ? [{ ...pick.quote, own: true }] : [];
    const current = [...own, ...(rows || []).filter(r => !heldRow(r) && officialKey(r) === officialKey(pick) && bookLabel(r.book) === bookLabel(pick.book) && r.state === 'open' && isNum(r.odds))]
      .filter(r => Date.parse(r.observedAt) <= now && now - Date.parse(r.observedAt) <= 4 * 3600000)
      .sort((a,b) => Date.parse(b.observedAt)-Date.parse(a.observedAt) || Number(b.line===pick.line)-Number(a.line===pick.line))[0];
    if (!current) return null;
    const cents = n => n < 0 ? n + 100 : n - 100;
    const pastPrice = current.line === pick.line && isNum(pick.cutoffOdds) && cents(current.odds) < cents(pick.cutoffOdds);
    const pastLine = isNum(pick.cutoffBoundary) && (pick.direction === 'under' ? current.line <= pick.cutoffBoundary : current.line >= pick.cutoffBoundary);
    return { current, inside: isNum(pick.cutoffOdds) && !pastPrice && !pastLine };
  };
  /* The Climb's status words, from the full rung ledger or today-hero.json's summary of it. */
  const climbWords = s => s.open ? `Step ${s.open.step || s.step} is live`
    : s.last && s.last.result === 'win' ? `Step ${s.last.step || s.step - 1} cashed · Step ${s.step} not posted yet`
      : s.last && s.last.result === 'loss' ? 'New $50 climb · Step 1 not posted yet'
        : s.settled ? `Step ${s.step} not posted yet` : 'The first step waits for two clean games';
  /* Today's first paint is for today's bets only. Future tickets stay below the game-day view. */
  const OFF_RAIL = ['Line moved', 'Pulled', 'Withdrawn'];
  const heroBets = (hero, now = Date.now(), league = 'ALL') => {
    const today = C.dayOf(new Date(now).toISOString());
    const mine = ((hero || {}).bets || []).filter(b => b && b.id && C.dayOf(b.kickoff) >= today && (league === 'ALL' || b.league === league)
      && !OFF_RAIL.includes(C.pickState(b, now).word));
    const todays = mine.filter(b => C.dayOf(b.kickoff) === today);
    return { today: Boolean(todays.length), rows: todays };
  };

  /* ---------- Kitchen Ticket model (OWNER-DECISIONS 2026-10-07 item 22) ---------- */
  /* kit.team_panel (SPEC 5.4), ported exactly: banned gold/orange/brown primaries use the alternate, light ones the
     alternate or charcoal, reds darken x0.78, team greens darken until they can't pass for Kook'n green, and chalk
     text keeps 4.5:1. Returns [top, bottom, glow]. */
  const CHALK = '#F2F7F4', CHARCOAL = '#2A2F33', HOUSE = ['#173A2A', '#0A1B13', CHALK];
  const rgbOf = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  const pyRound = x => { const f = Math.floor(x), d = x - f; return d > .5 ? f + 1 : d < .5 ? f : f % 2 ? f + 1 : f; };
  const shade = (c, f) => '#' + rgbOf(c).map(v => Math.max(0, Math.min(255, pyRound(f <= 1 ? v * f : v + (255 - v) * (f - 1)))).toString(16).padStart(2, '0')).join('').toUpperCase();
  const lum = c => { const [r, g, b] = rgbOf(c).map(v => (v /= 255) <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4); return .2126 * r + .7152 * g + .0722 * b; };
  const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + .05) / (y + .05); };
  const hls = c => {
    const [r, g, b] = rgbOf(c).map(v => v / 255), mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
    if (!d) return [0, l, 0];
    const h = r === mx ? (mx - b) / d - (mx - g) / d : g === mx ? 2 + (mx - r) / d - (mx - b) / d : 4 + (mx - g) / d - (mx - r) / d;
    return [((h / 6) % 1 + 1) % 1, l, l <= .5 ? d / (mx + mn) : d / (2 - mx - mn)];
  };
  const banned = c => { const [h, l, s] = hls(c); return h >= 8 / 360 && h <= 58 / 360 && s >= .22 && l >= .08 && l <= .9; };
  const hexOf = c => /^#?[0-9a-f]{6}$/i.test(String(c || '').trim()) ? '#' + String(c).trim().replace('#', '').toLowerCase() : null;
  const teamPanel = (primary, alternate) => {
    let color = hexOf(primary) || CHARCOAL;
    const alt = hexOf(alternate);
    if (banned(color)) color = alt && !banned(alt) ? alt : CHARCOAL;
    if (lum(color) > .6) color = alt && lum(alt) < .4 && !banned(alt) ? alt : CHARCOAL;
    if (lum(color) < .012) return ['#1C1F23', '#060708', CHALK];
    const [h, , s] = hls(color);
    let top = (h < 15 / 360 || h > 335 / 360) && s >= .35 && lum(color) > .07 ? shade(color, .78) : color;
    while (contrast(CHALK, top) < 4.5) top = shade(top, .92);
    for (let g = hls(top); g[0] >= 85 / 360 && g[0] <= 175 / 360 && g[2] >= .3 && lum(top) > .06; g = hls(top)) top = shade(top, .9);
    return [top, shade(top, .34), lum(color) < lum('#0E2219') * 1.6 ? CHALK : color];
  };
  /* The split panel's two halves (SPEC 5.3). Two teams of one hue would read as one slab, so then the home team's
     alternate colour, else the away team's, else a darker home shade (each still passes teamPanel's rules). */
  const rgbGap = (a, b) => Math.hypot(...rgbOf(a).map((v, i) => v - rgbOf(b)[i]));
  const splitColours = g => {
    const away = teamPanel(g.away.color, g.away.alt)[0], home = teamPanel(g.home.color, g.home.alt)[0];
    if (rgbGap(away, home) >= 72) return [away, home];
    const homeAlt = hexOf(g.home.alt) ? teamPanel(g.home.alt, g.home.color)[0] : home;
    if (rgbGap(away, homeAlt) >= 72) return [away, homeAlt];
    const awayAlt = hexOf(g.away.alt) ? teamPanel(g.away.alt, g.away.color)[0] : away;
    return rgbGap(awayAlt, home) >= 72 ? [awayAlt, home] : [away, shade(home, .55)];
  };
  /* SPEC 5.1: the stacked unit beside the bet. */
  const STAT_UNITS = { recYds: ['REC', 'YDS'], rushYds: ['RUSH', 'YDS'], passYds: ['PASS', 'YDS'], passTD: ['PASS', 'TDS'], rec: ['RECS'],
    car: ['CARRIES'], cmp: ['COMP'], att: ['PASS', 'ATT'], rushRecYds: ['RUSH+REC', 'YDS'], total: ['TOTAL', 'PTS'] };
  const minus = s => String(s).replace(/(^|[\s(])-(?=\d)/g, '$1−');
  /* What the ticket prints: the player's name and "OVER 49.5" + unit, a total's side, or a spread's team and number. */
  const betParts = (pick, game = null) => {
    const title = String(pick.displayTitle || pick.title || ''), dir = String(pick.direction || '').toLowerCase();
    const line = pick.line != null && isNum(Number(pick.line)) ? Number(pick.line) : null;
    const m = title.match(/^(.*?)\s+(over|under)\s+([\d.]+)/i);
    if (pick.athleteId || pick.kind === 'props' || pick.kind === 'riskyProps') {
      const name = String(pick.player || (m ? m[1] : title.replace(/\s+anytime.*$/i, ''))).trim();
      const side = ['over', 'under'].includes(dir) ? dir : m ? m[2].toLowerCase() : '';
      const n = line != null ? line : m ? Number(m[3]) : null;
      return side && n != null ? { kind: 'prop', name, bet: `${side.toUpperCase()} ${n}`, unit: STAT_UNITS[C ? C.marketKey(pick) : pick.market] || [] }
        : { kind: 'prop', name, bet: /anytime/i.test(title) ? 'ANYTIME TD' : title.slice(name.length).trim().toUpperCase(), unit: [] };
    }
    if (pick.marketType === 'spread' && line != null) {
      const team = game && game[dir] && game[dir].abbr ? game[dir].abbr : title.split(/\s+[+−-]?\d/)[0];
      return { kind: 'spread', name: title.replace(/\s+[+−-]?[\d.]+(\s|$)/, ' ').trim(), bet: minus(`${team} ${line > 0 ? '+' : ''}${line}`), unit: [] };
    }
    if (m || pick.marketType === 'total') {
      const side = ['over', 'under'].includes(dir) ? dir : m ? m[2].toLowerCase() : '';
      return { kind: 'total', name: m ? m[1] : title, bet: `${side.toUpperCase()} ${line != null ? line : m ? m[3] : ''}`.trim(), unit: STAT_UNITS.total };
    }
    return { kind: 'other', name: title, bet: title.toUpperCase(), unit: [] };
  };
  /* Font sizes that fit a 375 px ticket: one-line names to 46 px, else two lines at most 24 px; the bet to 68 px. */
  const nameSize = (name, max = 46) => {
    const one = Math.floor(205 / (Math.max(1, name.length) * .42));
    /* Two lines plus the chip must clear the matchup row: at most 24 px (a 26-letter double-barrelled name fits). */
    return one >= 34 ? Math.min(max, one) : Math.max(20, Math.min(24, Math.floor(205 / (Math.max(...name.split(/\s+/).map(w => w.length), 1) * .42))));
  };
  const betSize = (parts, cap = 68) => Math.max(34, Math.min(cap, Math.floor(306 / (parts.bet.length * .41 + Math.max(0, ...parts.unit.map(u => u.length)) * .18))));
  const ET_PARTS = (iso, opts) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', ...opts }).format(new Date(iso));
  const etHour = iso => Number(ET_PARTS(iso, { hour: 'numeric', hourCycle: 'h23' })) % 24;
  const weekday = iso => ET_PARTS(iso, { weekday: 'long' });
  const COUNT = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten'];
  /* The chef's line over the rail: "One for tonight.", "Three for today.", or the next game day's count. */
  /* One tonight cutoff for the chef's line, the ticket's kickoff and the Prep List: 5 PM Eastern or later. */
  const TONIGHT = 17;
  const tonight = iso => etHour(iso) >= TONIGHT;
  const ledeTitle = (rows, today) => !rows.length ? 'Nothing on the rail yet.'
    : `${COUNT[rows.length] || rows.length} for ${!today ? weekday(rows[0].kickoff) : rows.every(r => tonight(r.kickoff)) ? 'tonight' : 'today'}.`;
  /* With a player photo hanging from the rail the breakout head sits beside the chef's line (NOTES 4.3: under about
     200 px at 32 px). Longer lines step the size down from a conservative width estimate; CSS caps the width too. */
  const ledeSize = title => title.length <= 16 ? null : Math.max(24, Math.floor(196 / (title.length * 0.4)));
  /* "Wednesday, Oct 7. Monday went 0-1." The last game day's W-L comes from the build (lastSlate). */
  const dateLine = (nowIso, last) => {
    const lastDay = last && last.day ? `${last.day}T16:00:00Z` : null;
    const gap = lastDay ? (Date.parse(C.dayOf(nowIso) + 'T16:00:00Z') - Date.parse(lastDay)) / 86400000 : 99;
    const wl = last ? `${last.wins}-${last.losses}${last.pushes ? `-${last.pushes}` : ''}` : '';
    return `${C.dayLabel(nowIso)}.${last ? ` ${gap <= 6 ? weekday(lastDay) : C.dayLabel(lastDay)} went ${wl}.` : ''}`;
  };
  /* A settled slip's detail: "Final 45-24, missed by 21." from the saved actual. The margin prints only when it agrees
     with the graded result (a book settlement can differ from the box score). */
  const resultLine = pick => {
    if (pick.resultDetail) return `${pick.resultDetail}.`;
    const a = String(pick.actual || ''), line = Number(pick.line), dir = String(pick.direction || '').toLowerCase();
    const score = a.match(/^(.+?) (\d+), (.+?) (\d+)$/), stat = a.match(/:\s*([\d.]+)\s/);
    const lead = score ? `Final ${score[2]}-${score[4]}` : stat ? `Had ${stat[1]}` : '';
    const value = score ? (pick.athleteId || pick.marketType !== 'total' ? null : Number(score[2]) + Number(score[4])) : stat ? Number(stat[1]) : null;
    if (!lead) return '';
    if (value == null || !isNum(line) || !['over', 'under'].includes(dir) || !['win', 'loss'].includes(pick.result)) return `${lead}.`;
    const cleared = dir === 'over' ? value > line : value < line, by = Math.abs(value - line);
    return cleared === (pick.result === 'win') && by ? `${lead}, ${cleared ? 'cleared' : 'missed'} by ${+by.toFixed(1)}.` : `${lead}.`;
  };

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
  const pctOne = x => isNum(x) ? `${(100 * x).toFixed(1)}%` : '–';
  const oddsText = x => x == null || x === '' || !Number.isFinite(Number(x)) ? '–' : Number(x) > 0 ? `+${Number(x)}` : String(Number(x));
  const upsetChanceLine = w => `We give them ${pctText(w.modelChance)} to win. Vegas has them at ${pctText(w.marketChanceNoVig)} once you take out the book's cut. At ${oddsText(w.odds)} you need ${pctOne(breakEven(w.odds))} to profit.`;

  /* Price age in plain words. Fresh ≤ 60 min, aging ≤ 4 h (the site's existing current-quote limit), else stale. */
  const quoteAge = (observedAt, kickoff, now = Date.now(), extra = {}) => {
    const at = Date.parse(observedAt);
    if (kickoff && Date.parse(kickoff) <= now) return { kind: 'started', minutes: null, label: 'Game started · saved pregame price' };
    if (extra.odds == null || extra.state === 'unpriced' || extra.state === 'reference') return { kind: 'unpriced', minutes: null, label: 'No price recorded' };
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
  const WHY_SKIP = /\braw\b|adjust|needed at|is needed|percentage points|projection is|reads \d|estimate|guarantee|confidence \d|\bedge is\b|units per unit|percentile|^Our (number|projection) is/i;
  /* Never a reason, whatever its prefix: uncalibrated chances and untested numbers. */
  const NEVER_WHY = /\d+(\.\d+)?% likely|tested against a line|uncalibrated|probably lower|true chance is|breaks even at|\b\d+ of (his|her|their|its)?\s*last \d+\b|\bin \d+ of (his|her|their|its) last \d+/i;
  /* Context, not support: shown with a neutral bullet, never a green check. */
  const CONTEXT = /^(Role|Defense|Matchup|Weather|Injury|Volume|Usage|Checked before publishing):/;
  const WATCH_SKIP = /not a guarantee|does not take the field|confidence \d+ of 10|games? this season\.?$|voided|in-game injury|handful of touches|estimated chance/i;
  const whyLines = pick => {
    if (pick?.modelLean && !pick.athleteId) return ((pick.reasoning || {}).context || []).filter(s => !NEVER_WHY.test(s)).slice(0, 2);
    const out = [];
    for (const value of (pick && pick.reasons) || []) {
      if (out.length >= 2) break;
      if (!HISTORY_SENTENCE.test(value) && !NEVER_WHY.test(value) && !WHY_SKIP.test(value)) out.push(String(value).trim());
    }
    if (pick && pick.reason && !/against this side/i.test(pick.reason) && !HISTORY_SENTENCE.test(pick.reason) && !NEVER_WHY.test(pick.reason)) out.push(String(pick.reason).trim());
    for (const s of sentences(pick && pick.why)) {
      if (out.length >= 2) break;
      if (/against this side/i.test(s) || HISTORY_SENTENCE.test(s) || NEVER_WHY.test(s)) continue;
      /* A defense line that the play's own caution says points against this side is not support. */
      if (/^Defense:/.test(s) && /positional allowance points against|defense (points|leans) against/i.test(String(pick.risk || ''))) continue;
      if (WHY_PREFIX.test(s) || !WHY_SKIP.test(s)) out.push(s.replace(/^Prop lean:\s*/i, ''));
    }
    return out.filter(s => (!WHY_SKIP.test(s) || WHY_PREFIX.test(s)) && !NEVER_WHY.test(s)).map(s => s.replace(/^Role: \d+(?:st|nd|rd|th) of [12] .*? by projected (\w+), ([\d.]+) a game\.$/, 'Role: $2 projected $1 a game.')).slice(0, 2);
  };
  const historyLine = pick => sentences(pick && pick.why).find(x => HISTORY_SENTENCE.test(x))
    || (pick && pick.reason && /\b\d+ of (his|her|their|its)?\s*last \d+\b|\bin \d+ of (his|her|their|its) last \d+/i.test(pick.reason) ? String(pick.reason).trim() : null)
    || ((pick && pick.reasoning && pick.reasoning.history) || null);
  const watchLine = pick => {
    const list = [...((pick && pick.cautions) || []), ...sentences(pick && pick.risk), ...((pick && pick.reasoning && pick.reasoning.cautions) || [])];
    const hit = list.find(s => !WATCH_SKIP.test(s) && !/^Our (number|projection) is [\d.]+\.?$/i.test(s));
    return hit ? hit.replace(/^Statistical counterpoint:\s*/i, '') : null;
  };

  /* The chain from our raw number to the chance we show, in words (the card face never shows the raw projection). */
  const howWeGotIt = pick => {
    const pap = (pick && pick.probabilityAtPublication) || {};
    const parts = [];
    if (isNum(pick && pick.projection) && isNum(pick && pick.line)) parts.push(`Our model projects ${round1(pick.projection)} against the ${pick.line} line.`);
    if (isNum(pap.rawChance) && isNum(pap.chance)) {
      parts.push(`On its own the model says ${pctOne(pap.rawChance)}. We trust only part of that${isNum(pap.calibration) ? ` (${Math.round(100 * pap.calibration)}% of its lean)` : ''}${isNum(pap.calibrationN) ? `, based on ${pap.calibrationN} graded lines like it` : ''}, so we show ${pctOne(pap.chance)}.`);
      if (isNum(pap.calibration) && pap.calibration < 0.5) parts.push('Our model runs hot in this market, so we cut it down hard.');
    }
    const needs = isNum(pap.breakEven) ? pap.breakEven : breakEven(pick && pick.odds);
    if (isNum(pap.chance) && isNum(needs)) { const e = edgePoints(pap.chance, needs); parts.push(`At ${oddsText(pick.odds)} the price needs ${pctOne(needs)}, so our chance is ${e > 0 ? '+' : ''}${e} points ${e >= 0 ? 'above' : 'below'} that.`); }
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
       the posted price, but that price is older than our freshness limit. "Closed": new entries stopped
       (line moved past its limit), pulled or withdrew it, or the game started. Only an open play gets the pitch. */
    const word = state.word;
    const mode = result ? 'settled' : state.tone === 'open' ? 'open' : word === 'Price expired' ? 'expired' : 'closed';
    const standing = mode === 'expired';
    const book = postedBook(pick.book);
    const at = `${oddsText(pick.odds)}${pick.book ? ` (${book})` : ''}`;
    const status = result ? word : mode === 'expired' ? 'Posted price may be gone' : word === 'Line moved' ? 'Off the card' : word === 'Pulled' ? 'Pulled before posting' : word;
    const statusNote = mode === 'expired' ? `Still on the card and graded at ${at}, the price we posted. That price is older than our freshness limit, so check your book before playing it.`
      : word === 'Line moved' ? (/graded/i.test(pick.entryNote || '') ? String(pick.entryNote).replace(/\.\.+/g, '.').trim()
        : `${pick.entryNote ? String(pick.entryNote).trim() + ' ' : 'Off the card. '}It is still graded at ${pick.line != null && !isParlayLike(pick) ? `${pick.line} ` : ''}${at}, the price we posted.`)
        : word === 'Pulled' ? (/graded/i.test(pick.entryNote || '') ? String(pick.entryNote).replace(/\.\.+/g, '.').trim() : `${pick.entryNote ? String(pick.entryNote).replace(/\.\.+/g, '.').trim() : 'Pulled over news before its post went out.'} It still counts and is graded at ${at}.`)
          : word === 'Withdrawn' ? `Withdrawn before kickoff.${pick.entryNote ? ' ' + pick.entryNote : ''}`
            : word === 'In play' ? (Date.parse(pick.kickoff) < now - 4 * 3600000 ? `Game over or running late · awaiting the result. Graded at ${at}, the price we posted.` : `In play. Graded at ${at}, the price we posted.`) : '';
    /* One line for compact tickets. */
    const graded = `graded at ${pick.line != null && !isParlayLike(pick) && word === 'Line moved' ? `${pick.line} ` : ''}${at}`;
    const awaitingResult = word === 'In play' && Date.parse(pick.kickoff) < now - 4 * 3600000;
    const statusShort = awaitingResult ? `Awaiting result · ${graded}` : mode === 'expired' ? goodTo(pick) || 'Posted quote is older than four hours' : word === 'Line moved' ? `Off the card · ${graded}` : word === 'Pulled' ? `Pulled before posting · ${graded}`
      : word === 'Withdrawn' ? 'Withdrawn before kickoff' : word === 'In play' ? `In play · ${graded}` : '';
    const stub = result === 'win' ? { cls: 'hit', big: '✓', small: 'Hit' }
      : result === 'loss' ? { cls: 'miss', big: '✗', small: 'Miss' }
        : result === 'push' || result === 'void' ? { cls: 'push', big: '–', small: result === 'void' ? 'Void' : 'Push' }
          : kind !== 'best' ? { cls: mode === 'open' ? 'fun' : 'closed', big: oddsText(pick.odds), small: mode === 'open' ? (kind === 'climb' ? 'Climb' : 'Fun') : mode === 'expired' ? 'Old price' : awaitingResult ? 'Awaiting result' : status }
            : mode === 'open' && chance != null ? { cls: 'open', big: pctText(chance), small: 'our chance' }
              : mode === 'open' ? { cls: 'open', big: oddsText(pick.odds), small: 'posted price' }
                : mode === 'expired' && chance != null ? { cls: 'closed', big: pctText(chance), small: 'at posted price' }
                  : mode === 'expired' ? { cls: 'closed', big: oddsText(pick.odds), small: 'posted price' }
                    : { cls: 'closed', big: pick.odds != null ? oddsText(pick.odds) : '•', small: awaitingResult ? 'Awaiting result' : status || 'Closed' };
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
    const sameLine = (row.books || []).filter(b => Number(b.line) === Number(row.line) && bookLabel(b.displayBook || b.book) && isNum(Number(b.odds)) && !/hard ?rock/i.test(b.book));
    const others = (row.books || []).filter(b => Number(b.line) !== Number(row.line) && bookLabel(b.displayBook || b.book));
    const best = row.bestSameLine || sameLine.slice().sort((a, b) => Number(b.odds) - Number(a.odds))[0];
    const age = quoteAge(row.observedAt, row.kickoff, now, { odds: row.odds, state: row.state, expiresAt: row.expiresAt });
    return {
      id: row.id, title: niceTitle(row.title), league: row.league, gameId: row.gameId, athleteId: row.athleteId || null,
      player: row.player || null, stat: row.stat || (C ? C.marketKey(row) : null), market: marketLabel(row), direction: row.direction || row.side || null,
      line: row.line, odds: row.odds, book: bookLabel(row.displayBook || row.book), kickoff: row.kickoff, state: row.state,
      bestOdds: best ? Number(best.odds) : null, bestBook: best ? bookLabel(best.displayBook || best.book) : null, booksCount: sameLine.length,
      otherLines: others.map(b => ({ book: bookLabel(b.displayBook || b.book), line: b.line, odds: b.odds })),
      chance: isNum(g.chanceDisplay) ? g.chanceDisplay : chance, needs, edge: isNum(g.edge) ? round1(g.edge) : edgePoints(chance, needs), fair: isNum(g.fairOdds) ? g.fairOdds : fairAmerican(chance),
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
  /* Does a defense rank support or work against the side of a bet? Uses the raw rank (allows more = soft) and
     needs three games, the same rule as the game page. */
  const defenseVerdict = (rawTone, dir, games) => { const d = String(dir || '').toLowerCase(); if (!(games >= 3) || !['over', 'under'].includes(d)) return null;
    if ((d === 'over' && rawTone === 'soft') || (d === 'under' && rawTone === 'tough')) return 'supports';
    return (d === 'over' && rawTone === 'tough') || (d === 'under' && rawTone === 'soft') ? 'opposes' : null; };
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
  /* Today's short research lists favor props, then sides, then a single total. The full Research board keeps
     every line and its own filters; this changes no posted play or quality gate. */
  const todayMarketRank = row => {
    if (row.isProp || row.athleteId || row.stat) return 0;
    const market = String(row.marketType || row.market || row.src?.marketType || row.src?.market || '').toLowerCase();
    return /total/.test(market) ? 2 : 1;
  };
  const todayResearchOrder = (rows, limit, compare) => {
    let totals = 0;
    return rows.slice().sort((a, b) => todayMarketRank(a) - todayMarketRank(b)
      || compare(a, b) || String(a.id || a.gameId || a.player).localeCompare(String(b.id || b.gameId || b.player)))
      .filter(row => todayMarketRank(row) !== 2 || ++totals <= 1).slice(0, limit);
  };
  /* Current, priced rows only; one per market and side, never held or already on the card. */
  const worthRows = (rows, official = new Set()) => todayResearchOrder(
    collapse(rows.filter(vm => hasValue(vm) && !heldRow(vm.src) && !official.has(vm.key))), 3, SORTS.edge);
  const SORTS = {
    edge: (a, b) => (b.edge ?? -99) - (a.edge ?? -99) || Date.parse(a.kickoff) - Date.parse(b.kickoff),
    chance: (a, b) => (b.chance ?? -1) - (a.chance ?? -1) || (b.edge ?? -99) - (a.edge ?? -99),
    kickoff: (a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff) || String(a.gameId).localeCompare(String(b.gameId)) || (b.edge ?? -99) - (a.edge ?? -99),
  };
  /* Heavy favorites: a "100%" trend at −900 still needs 90% to break even. Shown by default while the rule
     decides (R5); the Trends chip can hide them. */
  const heavyFavorite = odds => { const need = breakEven(odds); return need != null && need > 0.8; };
  const trendText = row => {
    const need = breakEven(row.odds);
    return `${row.hits} of ${row.games}${need != null ? ` · this price needs ${pctText(need)} to win often enough` : ' · no price recorded'}`;
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
  const MORE_PAGES = ['start', 'saved', 'arbs', 'lab', 'schedule', 'feedback', 'status', 'glossary'];
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
        const lineParams = ['type', 'sort', 'show', 'q'].some(key => params.has(key));
        const mode = a === '' ? (lineParams ? 'lines' : 'news') : ['lines', 'trends', 'players', 'news'].includes(a) ? a : 'lines';
        return { view: 'research', mode, type: params.get('type') || null, sort: params.get('sort') || null, q, game: params.get('game') || null, sub: params.get('view') || null, rate: params.get('rate') || null, show: params.get('show') || null, pl: (params.get('pl') || '').toUpperCase() || null,
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
      case 'stats': case 'charts': case 'players': return { view: 'research', mode: 'players', sub: a === 'defense' ? 'defense' : a === 'teams' ? 'teams' : ['search', 'players'].includes(a) || (q && !['stat', 'sample', 'date', 'position'].some(key => params.has(key))) ? 'search' : null, q,
        league: params.get('sport') ? params.get('sport').toUpperCase() : null, legacy: true, ctx: [...params.keys()].length && C && C.researchContext ? C.researchContext(`#stats?${params}`) : null };
      case 'defense': return { view: 'research', mode: 'players', sub: 'defense', legacy: true };
      case 'games': return { view: 'games', tab: ['live', 'final'].includes(a) ? a : 'upcoming', league: params.get('sport') ? params.get('sport').toUpperCase() : null };
      case 'scores': return { view: 'games', tab: 'live', league: a ? a.toUpperCase() : 'ALL', legacy: true };
      case 'sport': return { view: 'games', tab: 'live', league: (a || 'NBA').toUpperCase(), legacy: true };
      case 'game': return rest ? { view: 'game', id: rest.split('#')[0], anchor: rest.split('#')[1] || null } : { view: 'games', tab: 'upcoming' };
      case 'player': return { view: 'player', league: (a || 'NFL').toUpperCase() === 'CFB' ? 'CFB' : 'NFL', id: b,
        stat: params.get('stat') || null, season: params.get('season') || null, sample: params.get('sample') || null };
      case 'team': return { view: 'team', league: (a || 'NFL').toUpperCase() === 'CFB' ? 'CFB' : 'NFL', id: b };
      case 'record': return { view: 'record', tab: ['fun', 'climb', 'model', 'trials'].includes(a) ? a : 'official', anchor: a === 'calendar' ? 'calendar' : null };
      case 'results': return { view: 'record', tab: 'official', legacy: true };
      case 'model': return { view: 'record', tab: 'model', legacy: true };
      case 'vegas': return { view: 'vegas', league: a ? a.toUpperCase() : null };
      case 'more': case 'tools': return { view: 'more' };
      case 'responsible': return { view: 'more', legacy: true };
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
      return `#research/${route.mode}${tail ? '?' + tail : ''}`;
    }
    if (route.view === 'games') return `#games/live${route.league && route.league !== 'ALL' ? '?sport=' + route.league : ''}`;
    if (route.view === 'record') return route.tab === 'official' ? '#record' : `#record/${route.tab}`;
    if (route.view === 'more') return '#more';
    return null;
  };
  const TAB_OF = { today: 'today', pick: 'today', research: 'research', games: 'games', game: 'games', team: 'games', player: 'research',
    record: 'record', vegas: 'record', more: 'more', ticket: 'more' };
  MORE_PAGES.forEach(p => { TAB_OF[p] = 'more'; });
  TAB_OF.lab = 'record';

  const model = { splitColours, ledeSize, goodTo, latestPickQuote, holdOf, pickHold, heldWords, heldShort, heldQuote, afterPostingWords, priceMatch, averageGap, researchPrice, matchupSignals, breakEven, fairAmerican, edgePoints, pctText, pctOne, oddsText, upsetChanceLine, quoteAge, bookLabel, postedBook, marketLabel, niceTitle, sentences,
    whyLines, watchLine, historyLine, howWeGotIt, pickVM, lineVM, officialKey, onBoard, hasValue, defenseVerdict, collapse, SORTS, heavyFavorite, trendText, gapScore,
    cumulativeUnits, clvSummary, parseHash, resolve, canonical, TAB_OF, MORE_PAGES, isParlayLike, climbWords, heroBets,
    teamPanel, STAT_UNITS, betParts, nameSize, betSize, ledeTitle, dateLine, resultLine, minus, worthRows, todayMarketRank, todayResearchOrder };

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
  const bs = (v => v && typeof v === 'object' ? v : {})(saved.get('board', {}));
  const state = {
    league: P.league(saved.get('league', 'ALL')),
    board: { type: ['all', 'props', 'games'].includes(bs.type) ? bs.type : 'all', sort: ['edge', 'chance', 'kickoff'].includes(bs.sort) ? bs.sort : 'edge', show: bs.show === 'all' || (bs.show == null && bs.value === false) ? 'all' : 'value', limit: 40 },
    q: '', trends: { rate: '80', window: 'season', kind: 'main', heavy: true, stat: 'all', day: 'all', limit: 40 },
    players: { q: '', pos: 'WR', stat: 'recYds', scope: 'season', order: 'soft', sub: 'matchup', game: 'next', chartStat: 'recYds', chartPos: 'all', chartWindow: 'season', league: 'NFL' },
    games: { sort: 'bettable', all: false, q: '', day: null, status: 'all', upDay: null, nav: { window: 'all', close: false, conf: 'all' } }, player: { key: null, stat: null, season: 'current', window: 'all' },
    record: { season: 'current', phase: 'current', q: '', cal: { month: null, league: 'ALL', ledger: 'best', day: null } },
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
  let previousEvery = null;
  const allPicks = async () => {
    const today = await get('app/today.json');
    const record = today.historyFile ? await maybe(`app/${String(today.historyFile).replace(/[^a-z0-9._-]/gi, '')}`) : null;
    if (!record || !Array.isArray(record.picks)) {
      if (!previousEvery) return today.picks || [];
      const byId = new Map(previousEvery.map(p => [p.id, p]));
      (today.picks || []).forEach(p => byId.set(p.id, p));
      return [...byId.values()];
    }
    const byId = new Map(record.picks.map(p => [p.id, p]));
    (today.picks || []).forEach(p => byId.set(p.id, p));
    previousEvery = [...byId.values()];
    return previousEvery;
  };
  const teamDirectory = async league => {
    const teams = await maybe(`app/teams/${league}.json`);
    if (!teams || teams.defense || !teams.defenseFile) return teams;
    const file = String(teams.defenseFile).replace(/[^a-z0-9/_.-]|\.\./gi, '');
    const payload = await maybe(`app/${file}`);
    return payload && payload.defense ? { ...teams, defense: payload.defense } : teams;
  };

  const inLeague = row => state.league === 'ALL' || row.league === state.league;
  const FOOTBALL = ['NFL', 'CFB'];
  /* The public catalog is a small manifest plus one shard per football league.
     A sport page fetches only its league; cross-sport tools explicitly ask for both. */
  const lineData = async (league = state.league) => {
    const index = await maybe('app/lines.json');
    if (!index) return null;
    if (Array.isArray(index.lines)) return index; // old cached build during a deploy
    const files = index.files && typeof index.files === 'object' ? index.files : {};
    const wanted = FOOTBALL.includes(league) ? [league] : FOOTBALL;
    const shards = await Promise.all(wanted.map(l => files[l] === `lines-${l}.json` ? maybe(`app/${files[l]}`) : Promise.resolve(null)));
    if (shards.some((payload, i) => !payload || payload.league !== wanted[i] || !Array.isArray(payload.lines))) return null;
    return { generatedAt: index.generatedAt, lines: shards.flatMap(payload => payload.lines) };
  };
  const LEAGUE_NAME = { ALL: 'All sports', NFL: 'NFL', CFB: 'College football', NBA: 'NBA', WNBA: 'WNBA', CBB: 'College hoops', MLB: 'MLB', NHL: 'NHL', EPL: 'Premier League', MLS: 'MLS' };
  const todayISO = () => new Date().toISOString();
  const etDay = (offset = 0) => C.dayOf(new Date(Date.now() + offset * 86400000).toISOString());

  /* ---------- fragments ---------- */
  const ICON = {
    research: '<path d="M4 19V11"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/>',
    games: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M12 5v14M3 12h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
  };
  const svg = (name, size = 22) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[name]}</svg>`;
  const TABS = [['today', 'Today'], ['research', 'Research'], ['games', 'Games'], ['record', 'Record'], ['more', 'More']];
  const head = (eyebrow, title, sub = '', back = '') => `${back}<div class="page-head">${eyebrow ? `<p class="eyebrow">${esc(eyebrow)}</p>` : ''}<h1>${esc(title)}</h1>${sub ? `<p class="sub">${sub}</p>` : ''}</div>`;
  const section = (title, body, link = '', note = '') => `<section class="section"><div class="section-head"><h2>${esc(title)}</h2>${link}</div>${note ? `<p class="section-note">${note}</p>` : ''}${body}</section>`;
  const empty = (title, text, icon = 'clock') => `<div class="empty">${svg(icon, 34)}<div><h3>${esc(title)}</h3><p>${text}</p></div></div>`;
  const SEG_LABEL = { type: 'Line type', show: 'Lines shown', gup: 'Day', trendRate: 'Hit rate', trendWindow: 'History window', trendKind: 'Line kind', trendDay: 'Games', cpos: 'Position', cwin: 'History window', plg: 'League', pos: 'Position', dscope: 'Sample', dorder: 'Order',
    gsort: 'Sort games', gnav: 'Slate filter', rcal: 'Calendar', gday: 'Day', gstatus: 'Game status', pstat: 'Stat', pwin: 'Sample', stakeMode: 'Stake in' };
  const seg = (key, options, current) => `<div class="seg" role="group" aria-label="${esc(SEG_LABEL[key] || key)}">${options.map(([value, label]) =>
    `<button type="button" data-set="${esc(key)}:${esc(value)}" aria-pressed="${String(current) === String(value)}">${esc(label)}</button>`).join('')}</div>`;
  /* Secondary filters: open on a desktop, folded on a phone, with the current choices in the summary. */
  const filtersFold = (key, summary, inner) => `<details class="filters" data-box="filters:${key}"${typeof matchMedia === 'function' && matchMedia('(min-width: 760px)').matches ? ' open' : ''}><summary>Filters<span>${esc(summary)}</span></summary><div class="toolbar">${inner}</div></details>`;
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

  /* ---------- the Kitchen Ticket (design/site, NOTES.md section 4) ---------- */
  const FLAME = '<svg viewBox="0 0 14 18" aria-hidden="true"><path fill="#F2F7F4" d="M7 0C8 4 13 6 13 11.5 13 15.5 10.3 18 7 18 3.7 18 1 15.5 1 12 1 9 3 7.5 4 6c.2 2 1 3 2.2 3.5C6 6 5 3 7 0z"/></svg>';
  const CHEF = '<img class="kt-clip" src="kookn-chef-clip.png" alt="" width="54" height="54">';
  const MARK = { hit: '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 7.5l3.4 3.4L12 3.5" fill="none" stroke="#062B1C" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    miss: '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2L2 12" stroke="#07120D" stroke-width="3" stroke-linecap="round"/></svg>',
    hold: '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 7h10" stroke="#07120D" stroke-width="3" stroke-linecap="round"/></svg>' };
  const stampFor = result => result === 'win' ? `<span class="kt-stamp hit" aria-hidden="true">${MARK.hit}HIT</span>`
    : result === 'loss' ? `<span class="kt-stamp miss" aria-hidden="true">${MARK.miss}MISS</span>`
      : result ? `<span class="kt-stamp hold" aria-hidden="true">${MARK.hold}${result === 'void' ? 'VOID' : 'PUSH'}</span>` : '';
  const RESULT_WORD = { win: 'Hit', loss: 'Miss', push: 'Push', void: 'Void' };
  const clock = iso => ET_PARTS(iso, { hour: 'numeric', minute: '2-digit' });
  const ticketWhen = iso => {
    if (!iso) return '';
    const days = (Date.parse(C.dayOf(iso) + 'T16:00:00Z') - Date.parse(etDay() + 'T16:00:00Z')) / 86400000;
    return days === 0 ? `${tonight(iso) ? 'Tonight' : 'Today'} ${clock(iso)}` : days > 0 && days < 7 ? `${ET_PARTS(iso, { weekday: 'short' })} ${clock(iso)}` : whenShort(iso);
  };
  /* The kickoff countdown inside the last day (ported from the pre-Kitchen-Ticket ticket). */
  const countdown = iso => { const ms = Date.parse(iso) - Date.now(); if (!(ms > 0) || ms > 864e5) return '';
    const n = Math.ceil(ms / 6e4); return ms < 6e4 ? 'Kicks off in under a minute' : `Kicks off in ${n >= 60 ? `${Math.floor(n / 60)}h ` : ''}${n % 60}m`; };
  const CARD_PATH = /^data\/cards\/[\w.-]+\.png$/;
  const logoImg = (team, league) => { const src = logoUrl(team, league); return src ? `<img src="${esc(src)}" alt="" loading="lazy">` : ''; };
  const disc = (team, league) => team ? `<span class="kt-disc">${logoImg(team, league)}</span>` : '';
  const panelVars = ([top, bottom, glow]) => `--team:${top};--team-deep:${bottom};--glow:${glow}`;
  const odd = x => minus(oddsText(x));
  /* The game a play belongs to: today.json's card, else the teams the hero row carries for the first paint. */
  const gameOf = pick => GAMES.get(pick.gameId) || (pick.teams ? { league: pick.league, ...pick.teams } : null);
  const legParts = leg => { const t = niceTitle(typeof leg === 'string' ? leg : leg.title || leg.displayTitle || leg.selection || leg.player || '');
    const m = t.match(/^(.*?)\s+((?:over|under)\s+[\d.]+.*|[\d.]+\+.*|[+−-][\d.]+|anytime touchdown)$/i);
    return m ? [m[1], minus(m[2].replace(/anytime touchdown/i, 'anytime TD')).toUpperCase()] : [t, '']; };
  /* The compact hit strip: five bars on a 34 px plot, values under the bars, the line labelled at the end. */
  const strip = (h, line, dir) => {
    if (!h || !(h.v || []).length || !isNum(Number(line))) return '';
    const max = Math.max(...h.v, Number(line)) || 1, px = v => Math.max(2, 34 * Math.max(0, v) / max);
    const res = v => C.thresholdResult(v, Number(line), dir === 'under' ? 'under' : 'over', false);
    const cap = `${h.season[0]} of ${h.season[1]} this season`;
    return `<figure class="kt-strip" role="img" aria-label="This season: ${esc(h.v.join(', '))} against the ${esc(line)} line. ${esc(cap)}.">
      <div class="kt-bars" aria-hidden="true">${h.v.map(v => `<div class="col"><div class="bar ${res(v)}" style="height:${px(v).toFixed(1)}px"></div><b class="v ${res(v)}">${esc(v)}</b></div>`).join('')}
      <div class="line" style="bottom:${px(Number(line)).toFixed(1)}px"><span>${esc(line)}</span></div></div>
      <figcaption><b>${esc(cap)}</b>${h.last10 && h.last10[1] >= 6 ? `${esc(h.last10[0])} of his last ${esc(h.last10[1])}` : ''}</figcaption></figure>`;
  };
  /* The order ticket: chip, name and photo on the team panel, the bet, price and book, my chance against what the
     price needs, WHY and BUT (saved strings chosen at build time), the hit strip and the season record on the stub.
     opts: strip (show the hit strip), compact (smaller bet), season ({wins, losses, pushes}), lines (current quotes),
     onPage (the play page: h1 name, no link). */
  const ticket = (pick, opts = {}) => {
    const vm = pickVM(pick), g = gameOf(pick), parts = betParts(pick, g), league = pick.league || String(pick.gameId || '').split('-')[0];
    const climb = vm.kind === 'climb', fun = vm.kind === 'fun', best = vm.kind === 'best', info = pick.ladder || {};
    const chip = vm.featured ? 'Hot Plate (POTD)' : climb ? `80/20 Climb${info.run ? ` #${info.run}` : ''}` : fun ? (vm.lotto ? 'Fun ticket · Lotto' : 'Fun ticket') : 'Best bet';
    const chipHtml = `<p class="kt-chip">${vm.featured ? FLAME : ''}${esc(chip)}</p>`;
    const when = ticketWhen(pick.kickoff), matchup = g && g.away && g.home ? `${g.away.abbr} at ${g.home.abbr}` : '';
    const nameText = climb ? `Step ${info.step || ''}`.trim() : fun ? `${vm.legs.length} legs` : parts.name;
    const nameTag = opts.onPage ? 'h1' : 'h2', nameIn = opts.onPage || opts.sample ? esc(nameText) : `<a href="${esc(vm.href)}">${esc(nameText)}</a>`;
    const nameHtml = `<${nameTag} class="kt-name" style="--name-size:${nameSize(nameText)}px">${nameIn}</${nameTag}>`;
    const side = g && pick.side && g[pick.side] ? g[pick.side] : null;
    const photo = best && parts.kind === 'prop' && pick.athleteId && HEADSHOT[league] ? HEADSHOT[league](pick.athleteId) : null;
    let panel, style, after = '';
    if (best && parts.kind !== 'prop' && g && g.away && g.home) {
      style = `--team-a:${splitColours(g)[0]};--team-b:${splitColours(g)[1]}`;
      panel = `<div class="kt-panel kt-split">${chipHtml}<p class="kt-when">${esc(when)}</p>
        <span class="kt-half">${disc(g.away, league)}<b>${esc(g.away.name || g.away.abbr)}</b></span><span class="kt-at" aria-hidden="true">AT</span>
        <span class="kt-half">${disc(g.home, league)}<b>${esc(g.home.name || g.home.abbr)}</b></span>${opts.onPage ? `<h1 class="sr">${esc(vm.title)}</h1>` : `<h2 class="sr"><a href="${esc(vm.href)}">${esc(vm.title)}</a></h2>`}</div>`;
    } else {
      style = panelVars(side ? teamPanel(side.color, side.alt) : HOUSE);
      const img = photo ? `<img src="${esc(photo)}" alt="">` : '';
      panel = `<div class="kt-panel">${photo ? `<div class="kt-ph" aria-hidden="true">${img}</div>` : ''}${side ? `<span class="kt-logo" aria-hidden="true">${logoImg(side, league)}</span>` : ''}
        ${chipHtml}${nameHtml}<p class="kt-meta">${g && g.away ? `<span class="kt-discs">${disc(g.away, league)}${disc(g.home, league)}</span>` : ''}<span><b>${esc(matchup || (climb || fun ? vm.book || '' : ''))}</b>${esc(when)}</span></p></div>`;
      if (photo) after = `<div class="kt-ph kt-photo" aria-hidden="true">${img}</div>`;
    }
    /* The now line: the latest same-book quote and how far the posted price may go. An expired or moved quote never
       reads as open: closed plays show their state words instead. */
    /* Under review (decision 9; the A-22/A-23 hold): no now line, no chance and no ORDER UP, only the plain words. */
    const rows = opts.lines || todayExtras?.lines?.lines;
    const hold = best && !pick.result ? pickHold(pick, rows) : null;
    const latest = !pick.result && !climb && !fun && !hold ? latestPickQuote(pick, rows) : null;
    const afterHold = Boolean(hold?.afterPosting);
    const holdPrice = afterHold ? heldQuote(pick, rows) : null;
    const good = isNum(pick.cutoffOdds) ? `Still good to ${odd(pick.cutoffOdds)}.` : '';
    const nowLine = pick.result ? resultLine(pick) : afterHold
      ? `${afterPostingWords(hold)}${holdPrice ? ` Latest ${odd(holdPrice.odds)} at ${clock(holdPrice.observedAt)} at ${vm.book}.` : ''}`
      : hold ? heldShort(hold)
      : climb ? (isNum(Number(info.stake)) && isNum(Number(info.payout)) && info.payout ? `${money(info.stake)} → ${money(info.payout)} if it cashes.` : '')
        : ['open', 'expired'].includes(vm.mode) && latest ? `Now ${odd(latest.current.odds)} at ${clock(latest.current.observedAt)}. ${latest.inside ? good : `Past my ${odd(pick.cutoffOdds)} limit.`}`
          : vm.mode === 'open' ? good : vm.mode === 'expired' ? 'Posted price may be gone. Check your book.' : vm.statusShort || vm.status || '';
    const tense = !afterHold && (vm.mode === 'open' || (vm.mode === 'expired' && latest && latest.inside));
    const chance = best && (!hold || afterHold) && vm.calibrated && vm.chance != null && vm.needs != null
      ? `<p class="kt-lead kt-chance"><span>I ${tense ? 'have' : 'had'} it at<b class="num">${pctOne(vm.chance)}</b></span><i></i><span>the price ${tense ? 'needs' : 'needed'}<b class="num">${pctOne(vm.needs)}</b></span></p>` : '';
    /* The build already chose held-safe words (build_site.held_words); when the hold comes only from the board rows,
       a saved line that quotes a projection, chance or edge is left off, never reworded. */
    const heldSafe = (text, held) => held && !held.afterPosting && HELD_WORDS.test(text || '') ? null : text;
    const say = (tag, text, cls = '') => text ? `<p class="kt-say${cls}"><span class="kt-tag">${tag}</span><span>${esc(text)}</span></p>` : '';
    const legs = (climb || fun) && vm.legs.length ? `<ul class="kt-legs">${(pick.legs || []).slice(0, 8).map(l => { const [a, b] = legParts(l); return `<li><span>${esc(a)}</span>${b ? `<b>${esc(b)}</b>` : ''}</li>`; }).join('')}</ul>` : '';
    /* The countdown and the posted share card (its path from the build, as before), on one small line. */
    const cd = pick.result ? '' : countdown(pick.kickoff), card = CARD_PATH.test(opts.card || '') ? opts.card : '';
    const extra = cd || card ? `<p class="kt-cd">${esc(cd)}${cd && card ? ' · ' : ''}${card ? `<a href="${esc(card)}" target="_blank" rel="noopener">See the card ↗</a>` : ''}</p>` : '';
    const fit = betSize(parts, opts.compact ? 60 : 68);
    const bet = climb || fun ? legs : `<p class="kt-bet num" style="--bet-size:${fit}px;--bet-size-k:${(fit / 306).toFixed(4)}">${esc(parts.bet)}${parts.unit.length ? `<span class="kt-unit">${parts.unit.map(esc).join('<br>')}</span>` : ''}</p>`;
    const s = opts.season, record = s ? `${s.wins}-${s.losses}${s.pushes ? `-${s.pushes}` : ''}` : '';
    const stub = best && opts.more ? '' : best ? (record ? `<p class="kt-season">Best bets ${s.playoffs ? 'these playoffs' : 'this season'}<b class="num">${esc(record)}</b></p>` : '<p class="kt-season">Best bet</p>')
      : climb ? `<p class="kt-season">Banked this climb<b class="num">${money(info.banked)}</b></p>` : '<p class="kt-season">Tracked apart from best bets</p>';
    /* ORDER UP needs a live price. */
    const orderUp = best && !pick.result && !hold && tense ? '<span class="kt-orderup" aria-hidden="true">ORDER UP</span>' : '';
    const label = `${chip}: ${vm.title}, ${oddsText(vm.odds)}${vm.book ? ` at ${vm.book}` : ''}${pick.result ? `. ${RESULT_WORD[pick.result] || ''}` : hold && !afterHold ? '. Under review' : ''}`;
    return `<article class="kt-order${opts.compact ? ' compact' : ''}${vm.mode === 'closed' ? ' is-closed' : ''}${hold ? ' is-held' : ''}" style="${style}" aria-label="${esc(label)}">
      <div class="kt-shade"><div class="kt-paper">${panel}${bet}<div class="kt-cut"></div>
        <p class="kt-lead kt-price"><b class="kt-odds num">${esc(odd(vm.odds))}</b><i></i><b class="kt-book">${esc(vm.estimated ? `est. ${vm.book || ''}` : vm.book || '')}</b></p>
        <p class="kt-now">${esc(nowLine)}</p>${chance}${best ? say('WHY', heldSafe(pick.ticketWhy, hold)) + say('BUT', heldSafe(pick.ticketBut, hold), ' kt-but') : ''}
        ${opts.strip && best ? strip(pick.hitStrip, pick.line, String(pick.direction || '').toLowerCase()) : ''}
        ${stub || extra || orderUp ? `<div class="kt-perf"></div><div class="kt-stubrow"><div class="kt-stubl">${stub}${extra}</div>${orderUp}</div>` : ''}</div></div>
      ${after}${opts.clip ? CHEF : ''}${stampFor(pick.result)}</article>`;
  };
  const rail = (rows, opts = {}) => `<section class="kt-pass${opts.onPage ? ' on-page' : ''}" aria-label="${esc(opts.label || (rows.length > 1 ? 'Best bets on the rail' : rows.length && C.dayOf(rows[0].kickoff) === etDay() ? 'Today\'s best bet' : 'Best bet'))}"><div class="kt-rail" aria-hidden="true"></div>
    <div class="kt-tickets">${rows.map((p, i) => ticket(p, { ...opts, card: p.card || (opts.cards && opts.cards.get(p.id)), clip: i === 0 && !opts.more, strip: i === 0 && !opts.more, compact: (i > 0 || opts.more) && !C.isLadder(p) })).join('')}</div></section>`;
  const HOOK = '<svg class="kt-hook h%" viewBox="0 0 26 22" aria-hidden="true"><path d="M7 0v8M19 0v8" stroke="#8C9892" stroke-width="2"/><rect x="1" y="6" width="24" height="13" rx="2.5" fill="#A3AEA8"/><rect x="3" y="15.5" width="20" height="2" rx="1" fill="#1E2622"/></svg>';
  const emptyRail = note => `<section class="kt-pass" aria-label="No best bet yet"><div class="kt-rail" aria-hidden="true"></div><div class="kt-hooks" aria-hidden="true">${HOOK.replace('%', '1')}${HOOK.replace('%', '2')}${CHEF}</div></section><p class="kt-blank">${note}</p>`;
  const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
  /* The 80/20 Climb stub: the chip carries the real stake; done steps get a check, the current one is outlined, the
     $1,000 flag stays visible. Never a guessed return or a promised step count. */
  const climbStub = (c, past = []) => {
    if (!c || !isNum(c.riding)) return '';
    const done = Math.max(0, Math.min(4, (c.step || 1) - 1));
    const state = c.open ? `Step ${c.open.step || c.step} is live` : 'Not posted yet';
    const n = c.settled || 0;
    const aside = `${c.last && c.last.result === 'win' && !c.open ? `Step ${c.last.step || c.step - 1} cashed. ` : ''}${c.saved ? `<strong>${money(c.saved)} banked.</strong> ` : ''}${n ? `Net ${signedMoney(c.net)} over ${WORDS[n] || n} step${n === 1 ? '' : 's'}. ` : ''}<a href="#record/climb">See the route ›</a>`;
    return `<section class="kt-sec kt-climb" aria-labelledby="climb-h"><h2 class="sr" id="climb-h">The 80/20 Climb</h2>
      <a class="kt-stub" href="#record/climb" aria-label="80/20 Climb number ${esc(c.run)}, step ${esc(c.step)}, ${esc(money(c.riding))}. ${esc(state)}.">
      <span class="kt-stub-chip"><span class="kt-pchip"><b>${money(c.riding)}</b></span></span><span class="kt-stub-main"><span class="kt-stub-e">80/20 Climb #${esc(c.run)}</span>
      <span class="kt-stub-k">Step ${esc(c.open ? c.open.step || c.step : c.step)}</span><span class="kt-stub-s">${esc(state)}</span>
      <span class="kt-route" aria-hidden="true">${'<span class="kt-node done">✓</span>'.repeat(done)}<span class="kt-node">${esc(c.step)}</span><span class="kt-trail"></span><span class="kt-flag"><svg viewBox="0 0 16 18"><path d="M2 1v16" stroke="#07120D" stroke-width="2.4" stroke-linecap="round"/><path d="M3 2h11l-3 3.5 3 3.5H3z" fill="#07120D"/></svg>$1,000</span></span></span></a>
      <p class="kt-aside">${aside}</p>${past.length ? `<details class="plain-fold" data-box="climb-past"><summary>Past steps · ${past.length}</summary><div class="receipts">${past.slice().reverse().map(climbRow).join('')}</div></details>` : ''}</section>`;
  };
  /* A slip: settled plays on the spike (with an equal-size stamp), open ones in the fold. */
  const slipTitle = (p, g) => { const parts = betParts(p, g);
    return isParlayLike(p) ? `<span>${esc(marketLabel(p))}</span> ${esc(odd(p.odds))}` : `<span>${esc(parts.kind === 'spread' ? '' : parts.name)}</span> ${esc(parts.bet)}${parts.kind === 'prop' && parts.unit.length ? ` ${esc(parts.unit.join(' '))}` : ''}`; };
  const slip = (p, opts = {}) => {
    const vm = pickVM(p), g = gameOf(p), kicker = `${vm.featured ? 'Hot Plate (POTD)' : vm.kind === 'fun' ? 'Fun ticket' : vm.kind === 'climb' ? '80/20 Climb' : 'Best bet'}${opts.when ? ` · ${ticketWhen(p.kickoff)}` : ''}`;
    const price = `${odd(p.odds)} ${vm.book || ''}`.trim();
    const resultName = p.resultDetail ? `${p.player || niceTitle(p.title || '').split(/\s+(?:OVER|UNDER)\s+/i)[0]} · ` : '';
    const detail = p.result ? `${resultName}${resultLine(p)} ${price}.` : opts.waiting ? `${price}.` : `${price}. ${vm.statusShort || (vm.mode === 'open' && vm.calibrated && vm.chance != null ? `I have it at ${pctOne(vm.chance)}.` : '')}`;
    const body = `<a class="kt-slip" href="${esc(vm.href)}" aria-label="${esc(`${p.result ? `${RESULT_WORD[p.result]}: ` : ''}${vm.title}, ${oddsText(p.odds)}${vm.book ? ` at ${vm.book}` : ''}`)}"><p class="kt-slip-k">${esc(kicker)}</p><p class="kt-slip-t">${slipTitle(p, g)}</p><p class="kt-slip-d">${esc(detail.trim())}</p>${opts.waiting ? '<span class="kt-waiting">WAITING ON THE FINAL</span>' : ''}</a>`;
    return opts.spike ? `<div class="kt-spiked"><span class="kt-spike" aria-hidden="true"></span>${body}${stampFor(p.result)}</div>` : body;
  };
  /* Leftovers: up to three settled slips (so the Prep List stays within one short scroll, decision 10), never dropping
     a miss while a hit stays, then "+N more on the record". The headline keeps the whole day's W-L. */
  const LEFTOVERS = 3;
  const leftovers = (settled, waiting, last) => {
    if (!settled.length && !waiting.length) return '';
    const misses = settled.filter(p => p.result === 'loss'), rest = settled.filter(p => p.result !== 'loss');
    const shown = [...misses, ...rest].slice(0, LEFTOVERS).sort((a, b) => String(b.kickoff).localeCompare(String(a.kickoff)));
    const more = settled.length - shown.length;
    const t = last || (settled.length ? { day: C.dayOf(settled[0].kickoff), wins: settled.filter(p => p.result === 'win').length, losses: misses.length, pushes: settled.filter(p => p.result === 'push').length } : null);
    const u = t && (isNum(t.units) ? t.units : last ? null : C.summaryOf(settled.filter(p => C.dayOf(p.kickoff) === t.day && !C.isUnpricedImport(p)), 1).units);
    const head = t ? `${weekday(`${t.day}T16:00:00Z`)} went ${t.wins}-${t.losses}${t.pushes ? `-${t.pushes}` : ''}${isNum(u) ? ` · ${units(u)}` : '.'}` : 'Waiting on the final.';
    return `<section class="kt-sec kt-left" aria-labelledby="left-h"><h2 class="kt-head" id="left-h">${esc(head)}</h2>
      ${waiting.map(p => slip(p, { spike: true, waiting: true })).join('')}${shown.map(p => slip(p, { spike: true })).join('')}
      <a class="kt-quiet" href="#record">${more > 0 ? `+${more} more on the record ›` : 'The full record ›'}</a></section>`;
  };
  const STAT_SHORT = { recYds: 'rec yds', rushYds: 'rush yds', passYds: 'pass yds', rec: 'receptions', car: 'carries', cmp: 'completions', att: 'pass attempts', passTD: 'pass TDs' };
  /* The Prep List: rows the build chose (today.json prep), chalked on the felt with the one tape label. */
  const prepList = (prep, notes, now) => {
    /* Each league's first game day and the next one (build_site.prep_list); the first day with a row still to kick off. */
    const blocks = Object.values(prep || {}).flatMap(b => [b, b && b.next]).filter(b => b && (b.rows || []).length && (state.league === 'ALL' || b.rows[0].league === state.league))
      .map(b => ({ day: b.day, rows: b.rows.filter(r => Date.parse(r.kickoff) > now) })).filter(b => b.rows.length);
    const day = blocks.map(b => b.day).sort()[0];
    const rows = todayResearchOrder(blocks.filter(b => b.day === day).flatMap(b => b.rows), 3,
      (a, b) => b.hits / b.games - a.hits / a.games || b.games - a.games);
    if (!rows.length && !notes.length) return '';
    const kind = !rows.length ? 'Research notes' : day === etDay() ? `Research for ${rows.every(r => tonight(r.kickoff)) ? 'tonight' : 'today'}` : `Research for ${weekday(`${day}T16:00:00Z`)}`;
    return `<section class="kt-sec kt-prep" aria-labelledby="prep-h"><div class="kt-sec-head"><h2 class="kt-tape" id="prep-h">Prep List</h2><span class="kt-kind">${esc(kind)}</span></div>
      ${rows.length ? `<ol class="kt-rows">${rows.map(r => `<li><span class="kt-face" style="--tc:${esc(hexOf(r.teamColor) || '#15301F')}">${HEADSHOT[r.league] ? `<img src="${esc(HEADSHOT[r.league](r.athleteId))}" alt="" loading="lazy">` : ''}</span>
        <div><p class="kt-who"><a class="plain-link" href="#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(r.stat)}"><b>${esc(r.player)}</b></a> <span>${esc([r.team, r.pos].filter(Boolean).join(' '))}</span></p>
        <p class="kt-pline">${esc(`${r.direction === 'under' ? 'Under' : 'Over'} ${r.line} ${STAT_SHORT[r.stat] || r.stat}`)}</p><p class="kt-px">${esc(odd(r.odds))} ${esc(bookLabel(r.book) || '')}${r.clears ? '<span class="ok">✓ clears my price</span>' : '<span class="no">History only · no edge at this price</span>'}</p></div>
        <p class="kt-hits"><b class="num">${esc(r.hits)}</b>of ${esc(r.games)}</p></li>`).join('')}</ol>` : ''}
      ${rows.some(r => r.league === 'CFB') ? '<p class="kt-note">College injury news is thin.</p>' : ''}
      ${notes.slice(0, 3).map(n => `<p class="kt-note"><a href="${esc(n.href)}"><b>${esc(n.title)}</b></a> ${esc(n.text)}</p>`).join('')}
      <a class="kt-more-link" href="#research/trends">${day === etDay() ? 'Tonight\'s' : 'More'} other lines ›</a></section>`;
  };
  /* A visible Today section (no fold): a chalk heading, or the tape label that marks research, and an optional kind. */
  const ktSec = (id, title, body, { tape = false, kind = '', link = '' } = {}) => `<section class="kt-sec kt-rest kt-${id}" aria-labelledby="${id}-h"><div class="kt-sec-head"><h2 class="${tape ? 'kt-tape' : 'kt-head'}" id="${id}-h">${esc(title)}</h2>${kind ? `<span class="kt-kind">${esc(kind)}</span>` : ''}</div>${body}${link}</section>`;
  const ktLink = (href, text) => `<a class="kt-more-link" href="${esc(href)}">${esc(text)} ›</a>`;

  /* ROI at posted prices: units over plays staked (one unit each), only once ten priced plays are graded. */
  const roiOf = cap => cap.priced >= 10 && cap.staked > 0 && isNum(cap.units) ? 100 * cap.units / cap.staked : null;
  /* Owner decisions still open (HANDOFF §7 R7 and §13): closing-line value as a headline number and a public ROI.
     Until that is approved, CLV stays on Model vs market and the receipts, and ROI is not shown. */
  const OWNER_FLAGS = { clvHeadline: false, roi: false };
  const kpiStrip = (picks, board, rows = null, label = null) => {
    const archive = rows ? null : C.recordArchive(picks);
    const scoped = rows || archive.rows;
    const straight = scoped.filter(p => !C.isParlay(p));
    const rec = C.recordBreakdown(straight), recNow = C.theRecord(scoped);
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
      <div class="kpi"><small>Units</small><b class="num ${rec.captured.units < 0 ? 'red' : rec.captured.units > 0 ? 'green' : ''}">${esc(units(rec.captured.units))}</b><span>at posted prices · ${esc(wl(rec.captured))} with a recorded price${rec.captured.roi != null ? ` · ROI ${rec.captured.roi > 0 ? '+' : ''}${rec.captured.roi.toFixed(1)}%` : ''}</span></div>
      ${OWNER_FLAGS.clvHeadline ? `<div class="kpi"><small>Beat the closing line</small><b class="num">${clv.measured ? `${clv.beat} of ${clv.measured}` : '–'}</b><span>${clv.measured ? `${clv.tied} tied · ${clv.lost} lost` : 'not measured yet'}</span></div>`
        : `<div class="kpi"><small>Pick of the Day</small><b class="num">${esc(wl(potd))}</b><span>one featured play a day</span></div>`}
      <div class="kpi"><small>Last game day</small><b class="num">${recNow.lastDay ? esc(wl(recNow.lastDay)) : '–'}</b><span>this week ${esc(wl(recNow.week))}</span></div></div>` };
  };

  /* ---------- live scores (factual refresh only; odds and picks stay on stored snapshots) ---------- */
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

  /* ---------- Today: the Kitchen Ticket (OWNER-DECISIONS 2026-10-07 item 22) ---------- */
  const money = n => `$${Math.round(Number(n) || 0).toLocaleString('en-US')}`;
  const signedMoney = n => { const v = Math.round(Number(n) || 0); return `${v > 0 ? '+' : v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString('en-US')}`; };
  const currentUpset = (g, now) => g.upsetWatch && g.state === 'pre' && !g.completed && Date.parse(g.kickoff) > now
    && now >= Date.parse(g.upsetWatch.observedAt) && now - Date.parse(g.upsetWatch.observedAt) <= 4 * 3600000;
  const upsetRow = (g, rank) => {
    const w = g.upsetWatch;
    return `<div class="card upset"><p><a class="plain-link" href="#game/${esc(g.id)}"><b>${esc(w.team)} · ${esc(oddsText(w.odds))} to win outright</b></a>${rank === 1 ? ' <span class="badge research">Top upset signal</span>' : ''}</p>
      <p class="small" style="margin-top:2px">${esc(upsetChanceLine(w))}</p>
      ${(w.reasons || [])[0] ? `<p class="small" style="margin-top:4px">${esc(w.reasons[0])}</p>` : ''}
      <p class="small muted" style="margin-top:4px">${esc(whenShort(g.kickoff))} · ${esc(bookLabel(w.book) || w.book || '')} · other team ${esc(oddsText(w.opponentOdds))} · price checked ${esc(ago(w.observedAt))}</p>
      <details class="plain-fold upset-why" data-box="upset:${esc(g.id)}"><summary>Why it's flagged</summary>${(w.reasons || []).length > 1 ? `<ul class="fa">${w.reasons.slice(1, 4).map(r => `<li class="for">${esc(r)}</li>`).join('')}</ul>` : ''}
      <p class="small red" style="margin-top:4px">${esc((w.warnings || [w.caution || 'Our winner estimate has not yet proved more accurate than the book.']).join(' · '))}</p></details></div>`;
  };
  /* The free community card (AGENTS: the front-page conversion path): early best bets, Discord-only arb alerts, the public record. */
  const COMMUNITY = `<aside class="kt-sec kt-rest kt-community" aria-label="Join the Kook'n Discord"><p class="kt-kind">Free Kook'n Discord</p><p><b>Best bets land here about 10–15 minutes before X.</b> Arb alerts stay in Discord. Every result stays public on this site.</p>
    <p class="kt-cta"><a class="btn primary" href="https://discord.gg/ZnjubjsBPM" target="_blank" rel="noopener">Join the free Discord ↗</a><a href="https://x.com/keenkooks" target="_blank" rel="noopener">or follow @keenkooks on X ↗</a></p></aside>`;
  const DATA_TTL = 300000;
  let todayExtras = null, todayExtrasAt = 0, todayExtrasLoading = false;
  const queueTodayExtras = () => {
    if (todayExtrasLoading || (todayExtras && Date.now() - todayExtrasAt < DATA_TTL)) return;
    todayExtrasLoading = true;
    Promise.all([maybe('scoreboard.json'), lineData(), maybe('sports.json'), allPicks()])
      .then(([board, lines, sports, every]) => { todayExtras = { board, lines, sports, every }; todayExtrasAt = Date.now(); })
      .catch(() => { todayExtras = {}; todayExtrasAt = Date.now(); })
      .finally(() => { todayExtrasLoading = false; if (C.parseRoute(location.hash).view === 'today') render(true); });
  };
  /* Today's first paint: today-hero.json (a few kilobytes, requested by index.html as the page starts). */
  let heroLoaded = null, todayLanded = false;
  const heroFetch = () => {
    const early = window.krHero;
    if (early) { window.krHero = null; cache.set('app/today-hero.json', { at: Date.now(), promise: early }); }
    return maybe('app/today-hero.json').catch(() => null)
      .then(hero => { if (hero && Array.isArray(hero.bets)) heroLoaded = hero; return heroLoaded; });
  };
  const LOADING = '<p class="loading muted" role="status">Loading…</p>';
  /* A painted hero belongs to football Today in the league it was painted for; anything else clears it at once. */
  const dropHero = () => { const view = $('#view'); if (view && view.querySelector('.hero-first')) view.innerHTML = LOADING; };
  /* The top of Today, the same on the first paint and the full card, so nothing moves when today.json lands: the
     chef's line with the last game day's W-L, the first ticket on the rail, the Climb stub (inside the first screen
     at 375 x 812, DIRECTION-RULES section 5 as updated by decision 10), then the rest of the rail. */
  const todayTop = ({ rows, today, last, season, climb, lines, more = [], past = [], later = [], cards = null, proof = '', spotlight = '', nextSlate = '', nothingCleared = false }) => {
    const title = nothingCleared && !rows.length ? 'Nothing cleared my bar today.' : ledeTitle(rows, today), first = rows[0];
    const photo = first && first.athleteId && !C.isParlay(first) && HEADSHOT[first.league || String(first.gameId || '').split('-')[0]];
    const size = photo ? ledeSize(title) : null;
    return `<section class="kt-lede${photo ? ' with-photo' : ''}"><p class="date">${esc(dateLine(todayISO(), last))}</p><h1${size ? ` style="font-size:${size}px"` : ''}>${esc(title)}</h1>${state.league === 'ALL' ? '' : `<p class="kt-sport-hint">${esc(LEAGUE_NAME[state.league])} only · <a href="#today?sport=ALL">See all sports ›</a></p>`}</section>
      ${rows.length ? rail(rows.slice(0, 1), { season, lines, cards }) : emptyRail(nothingCleared ? "No best bet today. Tonight's games are below." : 'Nothing on the rail yet. Check back before kickoff.')}
      ${climbStub(climb, past)}${proof}${spotlight}${rows.length > 1 || more.length ? `<section class="kt-sec kt-rest kt-bets" aria-labelledby="bets-h"><h2 class="kt-head" id="bets-h">More best bets</h2>
      ${rail([...more, ...rows.slice(1)], { season, lines, cards, more: true, label: 'More best bets' })}</section>` : ''}${nextSlate}${later.length ? `<section class="kt-sec kt-rest kt-bets" aria-labelledby="upcoming-bets-h"><h2 class="kt-head" id="upcoming-bets-h">Upcoming best bets</h2>
      ${rail(later, { season, lines, cards, more: true, label: 'Upcoming best bets' })}</section>` : ''}`;
  };
  const firstPaint = (hero, now = Date.now()) => {
    const { today, rows } = heroBets(hero, now, state.league);
    /* Wait for the full game-day feed rather than flash a future ticket or assert an unevaluated empty rail. */
    if (!rows.length && ((hero || {}).bets || []).length) return '';
    return `<div class="hero-first kt-today" aria-busy="true"><div>${todayTop({ rows, today, last: (hero.last || {})[state.league], season: (hero.season || {})[state.league],
      climb: hero.climb })}</div><div><p class="loading muted" role="status">Loading the rest of today…</p></div></div>`;
  };
  /* Painted only while today.json is still on its way, and only if no newer render or route has started. */
  const paintHero = (heroP, todayP) => {
    const token = renderToken;
    let landed = false;
    todayP.then(() => { landed = true; }, () => { landed = true; });
    heroP.then(hero => {
      const view = $('#view');
      if (!hero || landed || token !== renderToken || !view || C.parseRoute(location.hash).view !== 'today') return;
      const html = firstPaint(hero);
      if (html) view.innerHTML = html; else dropHero();
    });
  };
  /* Sports without best bets get their own honest Today: the same chef's line over an empty rail, then that sport's
     trial and scores. Never football substituted. */
  const sportToday = async () => {
    const [lab, trials] = await Promise.all([maybe('market-lab.json'), maybe('app/sport-research.json')]);
    const lg = state.league;
    const card = trialCard(lg, lab, trials);
    const scores = await (await ensureGames()).gamesLive({ day: etDay() });
    const hasTrial = ((trials || {}).leagues || {})[lg], hasLab = ((lab || {}).leagues || {})[lg];
    const status = hasTrial ? 'in a paper trial, not official picks' : hasLab ? 'collecting data for a future model, not picks' : 'scores only for now: no picks or research yet';
    return `<section class="kt-lede"><p class="date">${esc(C.dayLabel(todayISO()))}. ${esc(LEAGUE_NAME[lg])}.</p><h1>Nothing on the rail yet.</h1></section>
      ${emptyRail(`No best bets in this sport. ${esc(LEAGUE_NAME[lg])} is ${esc(status)}. <a href="#record/trials">All sports' status ›</a>`)}
      <div class="kt-page-sec">${card}</div><div class="kt-page-sec">${scores}<p class="small" style="margin-top:12px"><a href="#games/live">All scores →</a></p></div>`;
  };
  /* Today, no fold (owner, 2026-10-07; AGENTS.md has the order). */
  VIEWS.today = async route => {
    if (route && route.league && location.hash !== appliedHash) { appliedHash = location.hash; setLeague(route.league); }
    if (!FOOTBALL.includes(state.league) && state.league !== 'ALL') { dropHero(); return sportToday(); }
    const todayP = get('app/today.json'), heroP = heroFetch();
    /* Until the full card has landed once, each Today render (a league change too) repaints the hero for its league. */
    if (!todayLanded) paintHero(heroP, todayP);
    const [today, notes] = await Promise.all([todayP, maybe('desk-notes.json'), heroP]);
    todayLanded = true;
    queueTodayExtras();
    const { board = null, lines = null, sports = null, every = today.picks || [] } = todayExtras || {};
    indexGames(today);
    const now = Date.now(), all = every, picks = all.filter(inLeague), sched = C.cardSchedule(picks, now);
    const pulled = p => p.status === 'withdrawn' || /before its post went out|^Pulled before posting:/.test(p.entryNote || '');
    /* Off the card after the line moved. It never hangs on the rail; it stays graded. A play whose
       saved quote only aged out is still on the card and hangs there with "Posted price may be gone". */
    const offCard = p => C.pickState(p, now).word === 'Line moved';
    const order = (a, b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)) || String(a.kickoff).localeCompare(String(b.kickoff));
    const straight = p => !C.isParlay(p) && !pulled(p);
    const todays = sched.today.filter(p => straight(p) && !offCard(p)).sort(order);
    const later = sched.upcoming.filter(p => straight(p) && !offCard(p)).sort(order);
    const off = [...sched.today, ...sched.upcoming].filter(p => straight(p) && offCard(p)).sort(order);
    const gone = [...sched.today, ...sched.upcoming, ...sched.awaiting].filter(p => !C.isLadder(p) && pulled(p));
    const awaiting = sched.awaiting.filter(p => !C.isLadder(p) && !pulled(p));
    const fun = [...sched.today, ...sched.upcoming].filter(p => C.isParlay(p) && !C.isLadder(p) && !pulled(p));
    /* A future bet must not become today's best bet just because today's bar cleared nothing. */
    const rows = todays;
    const rest = later;
    const ladder = C.theLadder(all);
    const rungHere = ladder.open && (state.league === 'ALL' || ladder.open.league === state.league) ? [ladder.open] : [];
    const climb = { run: ladder.run, step: ladder.step, riding: ladder.open ? Number((ladder.open.ladder || {}).stake) || ladder.stake : ladder.stake,
      open: ladder.open && { step: (ladder.open.ladder || {}).step }, settled: ladder.history.length, saved: ladder.saved, net: ladder.accounting.net,
      last: ladder.history.length ? { result: ladder.history[ladder.history.length - 1].result, step: (ladder.history[ladder.history.length - 1].ladder || {}).step } : null };
    const games = (today.games || []).filter(inLeague);
    /* Show the nearer football slate before a later posted ticket. A saved NFL-only filter must not make
       Monday's ticket look like the next thing happening when Sunday has a full schedule. */
    const futureGames = games.filter(g => !g.completed && C.dayOf(g.kickoff) > etDay()).sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)));
    const futureDays = [...new Set(futureGames.map(g => C.dayOf(g.kickoff)))].sort();
    const firstLaterDay = rest.map(p => C.dayOf(p.kickoff)).filter(Boolean).sort()[0];
    const beforeBet = firstLaterDay ? futureDays.filter(day => day < firstLaterDay) : [];
    const nextDays = (beforeBet.length ? beforeBet : futureDays).slice(0, 2);
    const nextSlate = nextDays.length ? ktSec('next', 'Next football', `<div class="kt-next-days">${nextDays.map(day => {
      const dayGames = futureGames.filter(g => C.dayOf(g.kickoff) === day);
      const counts = [['CFB', 'college'], ['NFL', 'NFL']].map(([lg, label]) => {
        const n = dayGames.filter(g => g.league === lg).length;
        return n ? `${n} ${label} game${n === 1 ? '' : 's'}` : '';
      }).filter(Boolean).join(' · ');
      const sample = dayGames.slice(0, 2).map(g => `${g.away.name} at ${g.home.name}`).join(' · ');
      return `<a class="kt-next-day" href="#games"><b>${esc(C.dayLabel(day + 'T12:00:00Z'))}</b><span>${esc(counts)}</span><small>${esc(sample)}</small></a>`;
    }).join('')}</div>`, { kind: 'Schedules and projections · not picks', link: ktLink('#games', 'See all games') }) : '';
    const graded = picks.filter(p => p.result && !p.historicalImport && !C.isParlay(p) && C.dayOf(p.kickoff));
    const lastDay = graded.map(p => C.dayOf(p.kickoff)).filter(d => d < etDay()).sort().pop();
    const recent = graded.filter(p => C.dayOf(p.kickoff) === lastDay || C.dayOf(p.kickoff) === etDay());
    const k = kpiStrip(all.filter(inLeague), board);
    const notesList = C.deskNotes(notes, state.league, now, today.games || []);
    /* Underdog watch: fresh outright candidates (both moneylines within four hours), and spread covers kept apart. */
    const current = vm => vm.age.kind === 'fresh' || vm.age.kind === 'aging';
    const withGame = vm => { const g = GAMES.get(vm.gameId); vm.matchup = g && g.away ? `${g.away.abbr} at ${g.home.abbr}` : null; return vm; };
    const lineRows = lines ? (lines.lines || []).map(r => withGame(lineVM(r, now))).filter(vm => inLeague(vm) && onBoard(vm, now) && current(vm)) : [];
    const upsets = games.filter(g => currentUpset(g, now)).sort((a, b) => (b.upsetWatch.modelChance - b.upsetWatch.marketChanceNoVig) - (a.upsetWatch.modelChance - a.upsetWatch.marketChanceNoVig)).slice(0, 4);
    const dogSpreads = lineRows.filter(vm => !vm.isProp && /spread/i.test(vm.market) && Number(vm.line) > 0 && hasValue(vm));
    const dogDay = dogSpreads.length ? C.dayOf(dogSpreads.slice().sort((a, b) => String(a.kickoff).localeCompare(String(b.kickoff)))[0].kickoff) : null;
    const spreadRows = dogSpreads.filter(vm => C.dayOf(vm.kickoff) === dogDay).sort(SORTS.edge).slice(0, 4);
    const upsetHtml = upsets.length || spreadRows.length ? `<p class="eyebrow" style="margin-bottom:8px">Outright upset candidates</p>${upsets.length ? `<div class="grid two">${upsets.map((g, i) => upsetRow(g, i + 1)).join('')}</div>` : '<p class="muted small">No fresh outright candidate.</p>'}
      ${spreadRows.length ? `<p class="eyebrow" style="margin:16px 0 4px">Underdog spread value</p><p class="small muted" style="margin-bottom:8px">Covering does not mean winning outright.</p><div class="board">${spreadRows.map(vm => boardRow(vm, false)).join('')}</div>` : '<p class="muted small" style="margin-top:10px">Underdog spreads: none highlighted right now.</p>'}`
      : '<p class="muted small">No current outright-upset or underdog-spread highlight.</p>';
    /* Research worth a look: the old Today's top three price-checked lines, never a play already on the card. */
    const official = new Set(picks.filter(p => !p.result && !p.historicalImport && !C.isParlay(p)).map(officialKey));
    const worth = worthRows(lineRows, official);
    /* Today's games: live first, scores refreshed from the free scoreboard, with our projected score. */
    const liveToday = withLive(games.filter(g => C.dayOf(g.kickoff) === etDay() || (!g.completed && (g.state === 'in' || C.dayOf(g.kickoff) === etDay(-1)))));
    const todayGames = liveToday.games.filter(g => C.dayOf(g.kickoff) === etDay() || g.state === 'in');
    const rank = g => g.state === 'in' ? 0 : !g.completed ? 1 : 2;
    /* A game without an official play still belongs on Today. Put today's NFL matchup immediately after the
       first ticket and Climb, ahead of future-day bets and research. Do not show it again in the games list. */
    const nflNow = todayGames.filter(g => g.league === 'NFL').sort((a, b) => rank(a) - rank(b) || String(a.kickoff).localeCompare(String(b.kickoff))).slice(0, 2);
    const spotlightIds = new Set(nflNow.map(g => g.id));
    const otherGames = todayGames.filter(g => !spotlightIds.has(g.id));
    const shown = otherGames.slice().sort((a, b) => rank(a) - rank(b) || String(a.kickoff).localeCompare(String(b.kickoff))).slice(0, 6);
    const nflSpotlight = nflNow.length ? ktSec('nfl-now', nflNow.some(g => etHour(g.kickoff) >= 17) ? "Tonight's NFL" : "Today's NFL",
      `<div class="projs">${nflNow.map(g => projCard(g, { ranks: false })).join('')}</div>`,
      { kind: 'Matchup and lines · not a best bet', link: ktLink('#games', 'All games today') }) : '';
    const slips = list => `<div class="kt-slips">${list.map(p => slip(p, { when: true })).join('')}</div>`;
    /* The season line counts every published play (record.json), so its units wait for that; the W-L shows at once. */
    const full = Boolean(todayExtras && todayExtras.every), s = (today.season || {})[state.league];
    const u = full ? k.rec.captured.units : null, wlText = full ? wl(k.rec.all) : s ? wl(s) : '';
    const proof = wlText ? `<p class="kt-proof"><a href="#record">${k.label === 'Playoff record' ? 'Playoffs ' : k.label === 'Season record' ? '' : 'This stage '}<b class="num">${esc(wlText.replace(/–/g, '-'))}</b>${isNum(u) ? ` · <span class="${u < 0 ? 'neg' : u > 0 ? 'pos' : ''}">${esc(units(u).replace(/u$/, ' units'))}</span> at posted prices` : ''} · <span class="go">Every result ›</span></a></p>` : '';
    const cards = new Map(((heroLoaded || {}).bets || []).map(b => [b.id, b.card]));
    const rest2 = [
      leftovers(recent, awaiting, (today.lastSlate || {})[state.league]),
      prepList(today.prep, notesList, now),
      ktSec('upsets', 'Underdog watch', upsetHtml, { tape: true, kind: 'Upset research, not best bets' }),
      ktSec('worth', 'Research worth a look', worth.length ? `<div class="board">${worth.map(vm => boardRow(vm, false)).join('')}</div>` : '<p class="kt-blank">Nothing on the board clears our price check right now.</p>',
        { tape: true, kind: 'Not best bets', link: ktLink('#research/lines', 'See every line') }),
      shown.length ? ktSec('games', nflNow.length ? 'Other games today' : "Today's games", `${liveStamp(liveToday.refreshed)}<div class="projs">${shown.map(g => projCard(g, { ranks: false })).join('')}</div>`,
        { link: ktLink(otherGames.length > shown.length ? '#games' : '#games/live', otherGames.length > shown.length ? `All ${todayGames.length} games today` : 'Live scores') }) : '',
      fun.length ? ktSec('fun', 'Fun tickets', slips(fun), { kind: 'Smaller stake, apart from best bets' }) : '',
      gone.length ? ktSec('pulled', `Pulled before kickoff · ${gone.length}`, slips(gone), { kind: 'Pulled over news; each still counts' }) : '',
      off.length ? ktSec('off-card', `Off the card · ${off.length}`, slips(off), { kind: 'The line moved; each still counts at the price we posted' }) : '',
      COMMUNITY,
      state.league === 'ALL' ? ktSec('sports', 'More sports', `<div class="pill-row">${Object.keys(LIVE).map(key => { const n = ((((sports || {}).leagues || {})[key] || {}).games || []).filter(g => g.date === etDay()).length;
        return `<a class="pill" href="#today?sport=${esc(key)}">${esc(LEAGUE_NAME[key])}${FOOTBALL.includes(key) ? '' : ` · ${n} today`} →</a>`; }).join('')}</div>`) : ''].join('');
    const evaluated = today.generatedAt && C.dayOf(today.generatedAt) === etDay()
      && (etHour(today.generatedAt) > 9 || etHour(today.generatedAt) === 9
          && Number(ET_PARTS(today.generatedAt, { minute: '2-digit' })) >= 30);
    return `<div class="kt-today"><div>${todayTop({ rows, today: Boolean(todays.length), last: (today.lastSlate || {})[state.league], season: (today.season || {})[state.league],
      climb, lines: lines && lines.lines, more: rungHere, past: ladder.history, later: rest, cards, proof, spotlight: nflSpotlight, nextSlate,
      nothingCleared: Boolean(evaluated && !todays.length && !rows.length && todayGames.length) })}</div>
      <div>${rest2}</div></div>`;
  };

  /* ---------- a single best bet ---------- */
  VIEWS.pick = async route => {
    const [today, board, catalog] = await Promise.all([get('app/today.json'), maybe('scoreboard.json'), lineData('ALL')]);
    indexGames(today);
    let pick = (today.picks || []).find(p => p.id === route.id);
    if (!pick) pick = (await allPicks()).find(p => p.id === route.id);
    const back = '<a class="kt-back" href="#today">‹ Today</a>';
    if (!pick) return head('', 'Play not found', 'This play is not in the current window. Every published play stays on the <a href="#record">record</a>.', back);
    const vm = pickVM(pick);
    /* Under review (decision 9): no fair price, edge, chance or projection while the play's market is held. The posted
       price, the grading words and the delivery history stay. */
    const hold = vm.kind === 'best' ? pickHold(pick, catalog?.lines) : null;
    const how = hold ? [] : howWeGotIt(pick);
    const prose = v => v == null ? '' : typeof v === 'string' ? v : Array.isArray(v) ? v.map(prose).join(' · ') : typeof v === 'object' ? Object.entries(v).map(([k, x]) => `${k}: ${prose(x)}`).join(' · ') : String(v);
    const host = (u, i) => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (_) { return `Source ${i + 1}`; } };
    const sources = (pick.sources || []).filter(x => /^https:\/\//.test(x));
    const clv = (((board || {}).picks || {}).rows || []).find(r => r.id === pick.id);
    const research = C.pickResearchRoute ? C.pickResearchRoute(pick) : null;
    const game = (today.games || []).find(g => g.id === pick.gameId);
    const notices = [
      pick.priceAssumed ? `<b>Price assumed.</b> ${esc(pick.priceNote || 'No price was recorded for this play, so it counts at an assumed −115.')}` : '',
      vm.estimated ? '<b>Estimated price.</b> Combined odds are estimated from the leg prices we saw. Check the real ticket price at your book.' : '',
      clv && clv.clv != null ? `<b>Closing-line value: ${esc(clvWords(clv.clv))}.</b> We posted ${esc(clv.postedLine ?? '–')} at ${esc(oddsText(clv.postedOdds))} and the last number before kickoff was ${esc(clv.closeLine ?? '–')}${clv.closeOdds != null ? ` at ${esc(oddsText(clv.closeOdds))}` : ''}. ${clv.clv > 0 ? 'We got the better number, which is the part we control.' : clv.clv < 0 ? 'The market moved to a better number after we posted.' : ''}` : '',
      pick.earlyExit ? '<b>Early-exit credit.</b> A book promo refunded this loss. The headline record still counts it as −1u; credits are shown separately.' : '',
    ].filter(Boolean);
    const result = pick.result ? `<div class="card"><p><b>${esc(vm.status)}</b>${pick.resultDetail || pick.actual ? ` · ${esc(prose(pick.resultDetail ? `${pick.player || niceTitle(pick.title || '').split(/\s+(?:OVER|UNDER)\s+/i)[0]} · ${pick.resultDetail}` : pick.actual))}` : ''}</p>${pick.settlementReason ? `<p class="small muted" style="margin-top:4px">${esc(prose(pick.settlementReason))}</p>` : ''}${pick.settledAt ? `<p class="small muted" style="margin-top:4px">Settled ${esc(when(pick.settledAt))}</p>` : ''}</div>` : '';
    const chanceTitle = vm.chance != null ? `How we got ${pctOne(vm.chance)}` : 'How we got this';
    const projected = game && !hold && !C.isParlay(pick) && !pick.athleteId ? section('Our projected score now', `<p class="small muted" style="margin-bottom:8px">When posted: our number ${isNum(pick.projection) ? esc(C.fixed(pick.projection)) : '–'} against the ${esc(pick.line ?? '–')} line${vm.chance != null ? ` (${pctText(vm.chance)} our chance)` : ''}. The card below is today's model and market.</p>${projCard(game, { link: true, sideLabel: 'Current lean' })}`) : '';
    const sameGame = research === `#game/${pick.gameId}`;
    const isSaved = state.watchlist.some(r => r.key === 'pick:' + pick.id);
    const tape = (title, body) => `<section class="kt-page-sec"><h2 class="kt-tape">${esc(title)}</h2>${body}</section>`;
    /* Fair price and edge live here, one tap from Today (decision 2). */
    const price = vm.kind === 'best' && !hold && vm.fair != null && vm.calibrated && vm.mode !== 'closed'
      ? tape('My price', `<div class="kt-figs"><p><b class="num">${esc(minus(oddsText(vm.fair)))}</b>Price matching our chance</p><p><b class="num">${vm.edge > 0 ? '+' : ''}${esc(vm.edge)} pts</b>Chance vs price's need</p></div>`) : '';
    const started = Date.parse(pick.kickoff) <= Date.now();
    const sentAt = pick.delivery?.xAt || pick.delivery?.discordAt;
    const held = hold?.afterPosting ? tape('Since I posted', `<p class="kt-held-felt">I posted this at ${esc(clock(sentAt))} at ${esc(odd(pick.odds))}${vm.book ? ` at ${esc(vm.book)}` : ''}. ${esc(afterPostingWords(hold))} It still counts at that price.</p>`)
      : hold ? tape('The hold', `<div class="kt-figs"><span class="kt-stamp hold kt-inline" role="img" aria-label="Under review">${MARK.hold}UNDER REVIEW</span></div>
      <p class="kt-held-felt">${C.dayOf(pick.kickoff) === etDay() ? 'No grade from me tonight. ' : ''}${esc(heldWords(hold))}</p><p class="small muted" style="margin-top:6px">It stays on the card and is graded at ${esc(odd(pick.odds))}${vm.book ? ` at ${esc(vm.book)}` : ''}, the price we posted.</p>`) : '';
    /* A Climb step or fun ticket keeps its saved words with its real stake and return, settled or not. */
    const saved = [pick.reason, pick.why].find(x => typeof x === 'string' && x.trim());
    const stake = vm.kind !== 'best' && saved ? tape(vm.kind === 'climb' ? 'The stake' : 'The ticket', `<p>${esc(saved.trim())}</p>`) : '';
    const chart = vm.kind === 'best' && pick.athleteId && FOOTBALL.includes(pick.league) && C.marketKey(pick)
      ? tape('Hit history', `<div data-prop-history data-league="${esc(pick.league)}" data-athlete="${esc(pick.athleteId)}" data-stat="${esc(C.marketKey(pick))}" data-line="${esc(pick.line)}" data-dir="${esc(pick.direction || 'over')}" data-game="${esc(pick.gameId || '')}" data-before="${pick.result || started ? esc(C.dayOf(pick.kickoff) || '') : ''}"${hold ? ' data-held="1"' : ''}></div>`)
      : vm.history ? tape('Hit history', `<p class="small">${esc(vm.history)} ${esc((pick.reasoning || {}).historyNote || 'History, not a probability.')}</p>`) : '';
    return `${back}<p class="small muted">${esc(when(vm.kickoff))}${pick.quotedAt && vm.mode === 'open' ? ` · price quoted ${esc(ago(pick.quotedAt))}` : ''}</p>
      <div class="kt-page"><div style="margin-top:14px">${rail([pick], { onPage: true, lines: catalog?.lines, season: (today.season || {})[state.league] })}</div>
      ${result ? tape('Result', result) : ''}${price}${held}${stake}
      ${notices.length ? `<div class="card on-felt" style="margin-top:14px;display:grid;gap:8px">${notices.map(n => `<p class="small">${n}</p>`).join('')}</div>` : ''}
      ${how.length ? tape(chanceTitle, `<div class="card"><ol class="steps">${how.map(x => `<li>${esc(x)}</li>`).join('')}</ol>${vm.chance != null ? `<p class="small muted" style="margin-top:6px">When we posted: we gave it ${(100 * vm.chance).toFixed(1)}% to win. At ${esc(oddsText(vm.odds))}, the price needed ${vm.needs != null ? `${(100 * vm.needs).toFixed(1)}%` : 'an unknown chance'} to win often enough.</p>` : ''}</div>`)
        : vm.kind === 'best' && !hold && isNum(pick.projection) ? tape('Our number', `<div class="card"><p>We project ${esc(C.fixed(pick.projection))} against the ${esc(pick.line)} line. No chance estimate checked against results was saved for this play.</p></div>`) : ''}
      ${chart}${projected}
      ${vm.legs.length ? tape('Legs', `<div class="card"><ul class="fa">${vm.legs.map(l => `<li>${esc(l)}</li>`).join('')}</ul>${pick.correlation ? `<p class="small muted" style="margin-top:8px"><b>How the legs relate:</b> ${esc(prose(pick.correlation))}</p>` : ''}</div>`) : ''}
      ${(pick.why || pick.risk) && !hold ? `<details class="more-box" data-box="fullread" style="margin-top:20px"><summary>Our notes when we posted it</summary><div class="grid two"><div class="card"><p class="eyebrow green">Why</p><p style="margin-top:6px">${esc(prose(pick.why))}</p>${(pick.reasoning || {}).historyNote ? `<p class="small muted" style="margin-top:6px">${esc(pick.reasoning.historyNote)}</p>` : ''}</div><div class="card"><p class="eyebrow">What could go wrong</p><p style="margin-top:6px">${esc(prose(pick.risk))}</p></div></div></details>` : ''}
      ${pick.cutoff ? tape(vm.mode === 'open' && !hold ? 'Good to' : vm.kind === 'best' ? 'Was good to' : 'Entry rule', `<p>${esc(prose(pick.cutoff))}</p>${vm.mode === 'open' && !hold && goodTo(pick) ? `<p class="small muted" style="margin-top:4px">${esc(goodTo(pick))}</p>` : ''}`) : ''}
      ${tape('Where it stands', `${vm.statusNote && !hold ? `<p class="small">${esc(vm.statusNote)}</p>` : ''}<p class="small muted" style="margin-top:4px">${esc(C.deliveryText(pick) || 'No delivery evidence recorded.')}</p>`)}
      <div class="btn-row" style="margin-top:18px">${research ? `<a class="btn" href="${esc(research)}">${pick.athleteId ? 'Player page' : 'Matchup research'}</a>` : ''}${pick.gameId && game && !sameGame ? `<a class="btn" href="#game/${esc(pick.gameId)}">Game page</a>` : ''}<a class="btn" href="#record">Every result</a><button type="button" class="btn" data-watch-pick="${esc(pick.id)}" aria-pressed="${isSaved}" aria-label="${isSaved ? 'Unsave' : 'Save'} ${esc(vm.title)}">${isSaved ? '★ Saved' : '☆ Save'}</button></div>
      ${sources.length ? `<p class="small muted" style="margin-top:14px">Sources: ${sources.map((x, i) => `<a href="${esc(x)}" target="_blank" rel="noopener noreferrer">${esc(host(x, i))} ↗</a>`).join(' · ')}</p>` : ''}
      <p class="kt-social small">Best bets land in the <a href="https://discord.gg/ZnjubjsBPM" target="_blank" rel="noopener">free Kook'n Discord ↗</a> about 10–15 minutes before X. <a href="https://x.com/keenkooks" target="_blank" rel="noopener">Follow @keenkooks on X ↗</a></p>
      <p class="small muted" style="margin-top:10px">${C.isParlay(pick) ? (C.isLadder(pick) ? 'A Climb step, tracked in dollars apart from the best-bet record.' : 'A fun ticket at a smaller stake, kept out of the best-bet record.') : pick.priceAssumed ? 'Graded at one unit at an assumed −115; no price was recorded when it was posted.' : 'Graded at one unit, at the line and price we posted.'} The posted price is kept for grading even after the line moves.</p></div>`;
  };

  /* ---------- Research (B: one pro board) ---------- */
  const boardRow = (vm, expandable = true) => {
    const price = vm.bestOdds != null && vm.bestOdds > Number(vm.odds) ? `${oddsText(vm.bestOdds)}` : oddsText(vm.odds);
    const book = vm.bestOdds != null && vm.bestOdds > Number(vm.odds) ? vm.bestBook : vm.book;
    const ageCls = vm.age.kind === 'fresh' ? '' : 'stale', clears = vm.clears != null ? vm.clears : hasValue(vm);
    const badge = vm.official ? `<span class="badge best">Best bet${vm.officialLine != null && Number(vm.officialLine) !== Number(vm.line) ? ` at ${esc(vm.officialLine)}` : ''}</span>`
      : vm.onCard ? `<span class="badge research" title="Posted at ${esc(oddsText(vm.onCard.odds))}${vm.onCard.line != null ? `, line ${esc(vm.onCard.line)}` : ''} and graded there">On the card${vm.onCard.line != null && Number(vm.onCard.line) !== Number(vm.line) ? ` at ${esc(vm.onCard.line)}` : ''}</span>` : '';
    const summary = `<div class="row-main">
      <div class="row-title with-art">${artFor(vm, 'sm')}<div><b>${esc(vm.title)}${badge}${vm.alternate ? '<span class="badge research">Alternate</span>' : ''}</b><span>${esc(vm.market)}${vm.position ? ` · ${esc(vm.position)}` : ''}${vm.matchup && !vm.isProp ? ` · ${esc(vm.matchup)}` : ''} · ${esc(vm.league === 'CFB' ? 'College' : vm.league)} · ${esc(whenShort(vm.kickoff))}</span>${vm.sub ? `<span>${esc(vm.sub)}</span>` : ''}</div></div>
      <div class="row-price"><b class="num">${esc(price)}</b><span class="${ageCls}">${esc(book || '')}${vm.booksCount > 1 ? ` · ${vm.booksCount} books` : ''}${vm.age.kind !== 'fresh' ? ` · ${esc(vm.age.label)}` : ''}${isNum(vm.opened) && vm.opened !== Number(vm.line) ? ` · opened ${esc(vm.opened)}` : ''}</span></div>
      <div class="row-meter on-felt">${meter(vm.chance, vm.needs, true)}<span>${pctText(vm.chance)} our chance · ${pctText(vm.needs)} needed</span></div>
      <div class="row-edge ${clears ? 'clears' : vm.edge > 0 ? 'pos' : 'neg'}">${clears ? '<span aria-hidden="true">✓ </span>' : ''}${vm.edge != null ? `${vm.edge > 0 ? '+' : ''}${vm.edge}` : '–'}<small class="lbl"> pts vs price need</small>${clears ? '<span class="sr"> · passes our price check</span>' : ''}</div>
      <div class="row-fair num"><small class="lbl">our price </small>${esc(oddsText(vm.fair))}</div></div>`;
    if (!expandable) return `<a href="${vm.athleteId && FOOTBALL.includes(vm.league) ? `#player/${vm.league}/${encodeURIComponent(vm.athleteId)}${vm.stat ? `?stat=${encodeURIComponent(vm.stat)}` : ''}` : vm.gameId ? `#game/${encodeURIComponent(vm.gameId)}` : `#research/lines?q=${encodeURIComponent(vm.player || vm.title)}`}" style="color:inherit;display:block;border-bottom:1px solid var(--line)">${summary}</a>`;
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
          ${vm.src && (vm.src.books || []).filter(b => bookLabel(b.book)).length > 1 ? `<p class="small" style="margin-top:8px"><b>Prices we saw at other books:</b> ${(vm.src.books || []).filter(b => bookLabel(b.book) && isNum(Number(b.odds))).sort((a, b) => Number(b.odds) - Number(a.odds)).map(b => `${esc(bookLabel(b.book))} ${esc(oddsText(b.odds))}${Number(b.line) !== Number(vm.line) ? ` at ${esc(b.line)}` : ''}${/hard ?rock/i.test(b.book) ? ' (comparison only)' : ''}`).join(' · ')}</p>` : ''}
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
    if (state.board.show === 'all') q.set('show', 'all');
    if (state.q) q.set('q', state.q);
    if (state.league !== 'ALL') q.set('sport', state.league);
    return `#research/${mode === 'news' ? 'news' : 'lines'}${String(q) ? '?' + q : ''}`;
  };
  const shareLink = (mode, route) => `<a class="linkish" href="${esc(researchShare(mode, route))}" data-copy-link>Copy link</a>`;
  const RESEARCH_HEAD = {
    trends: ['Hit-rate trends', 'How often a player cleared a line in recorded regular-season games. History, not a probability.'],
    players: ['Players and matchups', "Each player's recent games against the current line, by matchup."],
    news: ['Injuries and news', 'ESPN injury list and status changes, newest first.'] };
  const researchHead = mode => {
    const [title, sub] = RESEARCH_HEAD[mode] || [state.board.show === 'value' ? 'Lines that pass our price check' : 'Every current line', 'Compare our estimated chance with how often the posted price needs to win. ✓ marks a line that passes our price check. Research is not a best bet unless it is labeled <span class="badge best">Best bet</span>.'];
    return `${head('Research', title, sub)}
      <div class="toolbar"><div class="chip-scroll">${segLinks([['#research/lines', 'Lines', 'lines'], ['#research/trends', 'Trends', 'trends'], ['#research/players', 'Players', 'players'], ['#research/news', 'News', 'news']], mode)}</div></div>`;
  };
  /* A link's filters apply once, when it is opened. After that the reader's own choices win, even on refresh. */
  let appliedHash = null;
  const NOT_YET = l => !FOOTBALL.includes(l) && l !== 'ALL';
  const notYet = () => empty(`${LEAGUE_NAME[state.league]} research is not available yet`, `Lines, trends and player research cover the NFL and college football. <a href="#games/live">Live scores</a> cover every sport, and new sports collect evidence in <a href="#record/trials">trials</a>.`, 'research');
  VIEWS.research = async route => {
    if (location.hash !== appliedHash) {
      appliedHash = location.hash;
      if (route.league) setLeague(route.league);
      if (route.type) state.board.type = route.type;
      if (route.sort && SORTS[route.sort]) state.board.sort = route.sort;
      if (route.q) { if (route.mode === 'players') { state.players.q = route.q; state.players.sub = 'search'; } else state.q = route.q; }
      if (route.mode === 'players') state.players.sub = ['defense', 'teams', 'search', 'matchup'].includes(route.sub) ? route.sub : route.q ? 'search' : 'matchup';
      if (route.pl === 'NFL' || route.pl === 'CFB') state.players.league = route.pl;
      if (route.rate && ['70', '80', '90', '100'].includes(route.rate)) state.trends.rate = route.rate;
      if (route.show === 'all' || route.show === 'value') state.board.show = route.show;
    }
    const today = await get('app/today.json');
    indexGames(today);
    const top = researchHead(route.mode);
    if (NOT_YET(state.league)) return top + notYet();
    const filtering = state.q ? `<p class="small" style="margin:0 0 10px">Filtering for <b>${esc(state.q)}</b> · <button type="button" class="linkish" data-clear-q>Clear</button></p>` : '';
    if (route.mode === 'trends') return top + filtering + await researchTrends(route);
    if (route.mode === 'players') return top + await researchPlayers(route);
    if (route.mode === 'news') return top + await researchNews();
    const lines = await lineData();
    if (!lines) return top + empty('Lines did not load', 'The current line files are unavailable right now. <button type="button" class="btn small" data-retry>Try again</button>', 'clock');
    const now = Date.now();
    const posted = new Map((today.picks || []).filter(p => !p.result && !p.historicalImport && !C.isParlay(p)).map(p => [officialKey(p), p]));
    const b = state.board;
    let rows = (lines.lines || []).filter(r => !r.roleSuspect && !r.priceSuspect).map(r => lineVM(r, now)).filter(vm => onBoard(vm, now) && inLeague(vm));
    const gameIndex = new Map((today.games || []).map(g => [g.id, g]));
    rows.forEach(vm => { const pk = posted.get(vm.key); vm.official = Boolean(pk && C.isOpen(pk)); vm.officialLine = pk ? pk.line : null; vm.onCard = pk && !vm.official ? pk : null; const g = gameIndex.get(vm.gameId); vm.matchup = g ? `${g.away.abbr} at ${g.home.abbr}` : null; vm.teams = g ? [g.away.name, g.home.name, g.away.abbr, g.home.abbr] : []; });
    if (b.type === 'props') rows = rows.filter(vm => vm.isProp);
    if (b.type === 'games') rows = rows.filter(vm => !vm.isProp);
    if (state.q) rows = rows.filter(vm => C.researchMatches(state.q, vm.title, vm.player, vm.market, vm.league, vm.matchup, ...vm.teams));
    /* Current prices only, as on Today; the count says how many older quotes are left out. */
    const current = rows.filter(vm => vm.age.kind === 'fresh' || vm.age.kind === 'aging');
    const older = collapse(rows).length - collapse(current).length;
    const isValue = vm => hasValue(vm) || vm.official;
    const nAll = collapse(current).length, nValue = collapse(current.filter(isValue)).length;
    rows = collapse(b.show === 'value' ? current.filter(isValue) : current).sort(SORTS[b.sort] || SORTS.edge);
    const shown = rows.slice(0, b.limit);
    /* By kickoff, rows sit under their game. */
    const grouped = b.sort === 'kickoff' ? shown.map((vm, i) => `${i === 0 || shown[i - 1].gameId !== vm.gameId ? `<div class="board-group">${vm.matchup ? `${esc(vm.matchup)} · ` : ''}${esc(whenShort(vm.kickoff))}</div>` : ''}${boardRow(vm)}`).join('') : shown.map(vm => boardRow(vm)).join('');
    /* Player lines the book has posted without a price we captured: research only, listed apart, never ranked. */
    const unpriced = b.show === 'value' || b.type === 'games' ? [] : (lines.lines || []).filter(r => r.state === 'unpriced' && (r.athleteId || r.player) && isNum(Number(r.line)) && r.line !== null && Date.parse(r.kickoff) > now && inLeague(r)
      && (!state.q || C.researchMatches(state.q, r.title, r.player, r.market, r.league)));
    const underReview = (lines.lines || []).filter(r => (r.roleSuspect || r.priceSuspect) && Date.parse(r.kickoff) > now && inLeague(r)
      && (!state.q || C.researchMatches(state.q, r.title, r.player, r.market, r.league)));
    const list = shown.length ? `<div class="board"><div class="board-head"><span>Line</span><span>Best price</span><span>Our chance vs needed</span><span>Chance gap</span><span>Our price</span></div>${grouped}</div>
      ${rows.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-more-rows>Show ${Math.min(40, rows.length - shown.length)} more</button></p>` : ''}`
      : empty('No lines match', b.show === 'value' ? 'Nothing passes our price check right now. Tap "Every current line" to see every current price.' : 'Try another sport or clear the search.', 'research');
    return `${top}
      <div class="toolbar">${seg('type', [['all', 'All'], ['props', 'Props'], ['games', 'Games']], b.type)}${seg('show', [['value', `Clears our bar · ${nValue}`], ['all', `Every current line · ${nAll}`]], b.show)}
        <div class="find-row"><label class="sr" for="sort">Sort</label><select id="sort" class="select" data-select="sort"><option value="edge"${b.sort === 'edge' ? ' selected' : ''}>Sort: biggest chance gap</option><option value="chance"${b.sort === 'chance' ? ' selected' : ''}>Sort: most likely</option><option value="kickoff"${b.sort === 'kickoff' ? ' selected' : ''}>Sort: kickoff</option></select>
        <div class="grow"><label class="sr" for="q">Search</label><input id="q" class="search" type="search" placeholder="Player, team or market" value="${esc(state.q)}" data-input="q" autocomplete="off"></div></div></div>
      <p class="small muted" style="margin-bottom:10px">${shown.length} of ${rows.length} lines${older ? ` · ${older} older prices hidden` : ''} · ✓ passes our price check · ${shareLink('lines', route)}</p>
      ${list}
      ${b.show === 'value' && rows.length < 5 && nAll > rows.length ? `<p class="small" style="margin-top:10px"><button type="button" class="linkish" data-set="show:all">See all ${nAll} current lines →</button></p>` : ''}
      ${unpriced.length ? `<details class="more-box" data-box="unpriced" style="margin-top:12px"><summary>Player lines with no price yet · ${unpriced.length}</summary><div class="receipts">${unpriced.slice(0, 60).map(r => `<div class="receipt" style="grid-template-columns:minmax(0,1fr) auto"><div><b>${r.athleteId ? `<a class="plain-link" href="#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}">${esc(niceTitle(r.title))}</a>` : esc(niceTitle(r.title))}</b><span>${esc(marketLabel(r))} · ${esc(whenShort(r.kickoff))}${isNum((r.grade || {}).projection) ? ` · our middle estimate ${esc(C.fixed(r.grade.projection))}` : ''}</span></div><span class="small muted">No price yet</span></div>`).join('')}</div><p class="small muted" style="margin-top:8px">The book lists these lines, but we have not seen a price, so we cannot compare our chance with what the price needs.</p></details>` : ''}
      ${underReview.length ? `<details class="more-box" data-box="under-review" style="margin-top:12px"><summary>Lines under review · ${underReview.length}</summary><div class="receipts">${underReview.slice(0, 60).map(r => `<div class="receipt"><b><a class="plain-link" href="#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(C.marketKey(r) || '')}">${esc(niceTitle(r.title))}</a></b><span>${esc(r.gradeNote || 'Projection under review')} · no grade or ranking</span></div>`).join('')}</div></details>` : ''}`;
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
    const cap = hasLine ? `${hit} of ${hit + miss + tie} ${word}${tie ? ` · ${tie} tied` : ''}. History, not a probability.` : 'No line recorded, so bars are not colored.';
    return `<div class="chart-wrap${geo.low < 0 ? ' has-neg' : ''}"><div class="chart" role="img" aria-label="${esc(cap)}">${zero}${lineEl}${cols}</div>
      <div class="chart-x">${labels.map(l => `<span>${esc(l)}</span>`).join('')}</div></div><p class="chart-cap">${esc(cap)}${hasLine && opts.legend !== false ? ' Green cleared it, red missed, gray tied or not recorded.' : ''}</p>`;
  };
  /* A defense's rank for this player's position and stat, in words, with a tone word so color is never the only cue. */
  /* A defense that allows more is good news for the player, except for stats that hurt him. */
  const BAD_FOR_PLAYER = new Set(['int', 'sacks', 'fumLost']);
  const toneFor = (rank, of, stat) => { const t = C.rankTone(rank, of); return BAD_FOR_PLAYER.has(stat) ? (t === 'soft' ? 'tough' : t === 'tough' ? 'soft' : t) : t; };
  /* College ranks count FBS defenses only, the same set as the Defenses table. */
  const defenseRows = (teams, league) => { const rows = ((teams || {}).defense || {}).rows || {};
    return league === 'CFB' ? Object.fromEntries(Object.entries(rows).filter(([id]) => (((teams || {}).teams || {})[id] || {}).fbs)) : rows; };
  const defGames = (rows, id, group, stat) => rows[id]?.coverage?.[group]?.[stat] ?? rows[id]?.g ?? 0;
  const defenseWords = (teams, oppId, pos, stat, league = null, dir = null) => {
    const group = C.POS_GROUP[pos], rowsL = teams && teams.defense ? defenseRows(teams, league) : null;
    const r = group && rowsL ? C.rankOf(rowsL, oppId, group, stat) : null;
    if (!r) return null;
    const tone = toneFor(r.rank, r.of, stat), v = defenseVerdict(C.rankTone(r.rank, r.of), dir, defGames(rowsL, oppId, group, stat));
    const name = ((teams.teams || {})[oppId] || {}).abbr || 'Opponent';
    return { tone, cls: v === 'supports' ? 'green' : v === 'opposes' ? 'red' : 'muted', text: `${name} allows ${C.fixed(r.value)} ${(STAT_WORD[stat] || C.LABEL[stat] || stat).toLowerCase()} a game to ${group}s · ${r.rank} of ${r.of}${league === 'CFB' ? ' FBS defenses' : ''} (1 allows the least)${tone === 'soft' ? ' · soft matchup' : tone === 'tough' ? ' · tough matchup' : ''}${v === 'supports' ? ` · supports the ${dir}` : v === 'opposes' ? ` · works against the ${dir}` : ''}` };
  };
  /* The player's own stored games this season against a line, plus the opponent's defense. For a game already
     played, only games before it count, so the picture is what was known at kickoff. */
  const propHistory = async (league, athlete, stat, line, dir, gameId, before = null, projection = null, held = false) => {
    const [index, teams, today] = await Promise.all([get(`app/players/${league}.json`), teamDirectory(league), get('app/today.json')]);
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
    const dw = opp && !before && !held && (!g || Date.parse(g.kickoff) > Date.now()) ? defenseWords(teams, opp.id, data.pos, stat, league, side) : null;
    const avg = list => { const v = list.map(read).filter(isNum); return { text: v.length ? C.fixed(v.reduce((a, b) => a + b, 0) / v.length) : '–', n: v.length }; };
    const a10 = avg(last), aS = avg(rows);
    return `<p class="eyebrow" style="margin-bottom:4px">This season vs ${esc(line)}${before ? ' · before this game' : ''}</p>
      ${historyChart(last.map(read), last.map(r => `${String(r[1]).slice(5)}\n${r[7] === 0 ? '@' : ''}${abbr(r[6])}`), line, side, { titles: last.map(r => `${r[1]} ${r[7] === 0 ? 'at' : 'vs'} ${abbr(r[6])}`) })}
      <p class="small" style="margin-top:6px"><b>${h10[side]} of ${h10.n}</b> last ${h10.n} · <b>${hs[side]} of ${hs.n}</b> this season${hs.n < 5 ? ' · small sample' : ''} · average ${esc(a10.text)} last ${a10.n}, ${esc(aS.text)} this season</p>
      ${isNum(projection) ? `<p class="small muted" style="margin-top:2px">Our average for this game: ${esc(C.fixed(projection))}. We shrink it before showing a chance.</p>` : ''}
      ${dw ? `<p class="small ${dw.cls}" style="margin-top:4px">${esc(dw.text)}</p>` : ''}
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
  const loadTrends = async (route, kind, dayFilter) => {
    const index = await get('app/trends/index.json');
    const wanted = (index.files || []).filter(file =>
      (state.league === 'ALL' || file.league === state.league) &&
      (kind === 'milestone' ? file.kind === 'milestone' : file.kind === 'priced') &&
      (route.game || dayFilter !== 'today' || file.date === etDay()));
    const payloads = await Promise.all(wanted.map(file => get(`app/trends/${file.file}`)));
    return payloads.reduce((all, payload) => ({ rows: all.rows.concat((payload.rows || []).map(row => ({
        ...((payload.contexts || {})[row.contextKey] || {}), ...row, historyKey: row.contextKey }))),
      histories: { ...all.histories, ...(payload.histories || {}) }, generatedAt: all.generatedAt }), { rows: [], histories: {}, generatedAt: index.generatedAt });
  };
  const researchTrends = async route => {
    const t = state.trends;
    /* A saved "Today" with no game today shows every upcoming game instead, without changing the saved choice. */
    const hasToday = ((await get('app/trends/index.json')).files || []).some(f => f.date === etDay() && (state.league === 'ALL' || f.league === state.league));
    const day = route.game || (t.day === 'today' && !hasToday) ? 'all' : t.day || 'all', fellBack = !route.game && t.day === 'today' && day === 'all';
    const data = await loadTrends(route, t.kind, day);
    const catalog = await lineData();
    const windowed = C.trendWindow(C.bestTrendPrices((data.rows || []).map(r => r.team && !r.team.abbr && r.team.abbreviation ? { ...r, team: { ...r.team, abbr: r.team.abbreviation } } : r)), t.window, data.histories);
    const pass = list => t.heavy ? list : list.filter(r => !heavyFavorite(r.odds));
    const forRate = rate => C.filterTrends(windowed, { min: 3, rate, league: state.league, stat: t.stat || 'all', kind: t.kind, day, game: route.game || null, query: state.q });
    const heavyCount = forRate(t.rate).filter(r => heavyFavorite(r.odds)).length;
    const rows = pass(forRate(t.rate));
    const limit = t.limit || 40;
    const shown = rows.slice(0, limit);
    const windowLabel = t.window === 'last5' ? 'last 5 this season' : t.window === 'last10' ? 'last 10 this season' : 'this season';
    const list = shown.length ? `<div class="grid two">${shown.map(r => {
      const hist = r.history || [];
      const atLeast = r.kind === 'milestone' || r.direction === 'at-least';
      const dir = atLeast ? 'at-least' : r.direction === 'under' ? 'under' : 'over';
      const what = atLeast ? `${r.line}+ ${STAT_WORD[r.stat] || r.stat}` : `${r.direction === 'under' ? 'Under' : 'Over'} ${r.line} ${STAT_WORD[r.stat] || r.stat}`;
      const price = r.kind === 'milestone' ? '<span class="badge research">Stat milestone</span> <span class="small muted">No verified price</span>'
        : `<b>${esc(oddsText(r.odds))}</b> ${esc(bookLabel(r.book) || '')} <span class="small muted">· checked ${esc(ago(r.observedAt))}</span>`;
      const playerHref = `#player/${esc(r.league)}/${esc(r.athleteId)}?stat=${esc(r.stat)}`;
      return `<div class="card"><div class="with-art" style="margin-bottom:4px">${headshot(r.league, r.athleteId, 'sm')}<p><a href="${playerHref}"><b>${esc(r.player || '')}</b></a> <span class="muted small">${esc(r.team?.abbr || r.team?.name || '')}</span>${heavyFavorite(r.odds) ? ' <span class="badge warn">Heavy favorite</span>' : ''}</p></div>
        <p style="font-weight:600">${esc(what)}</p>
        <p class="small" style="margin:2px 0">${price}</p>
        ${r.qbNews ? `<p class=caution>QB news: ${esc(r.qbNews)}</p>` : ''}
        ${r.kind !== 'milestone' ? `<p class="small">${esc(researchPrice(priceMatch(r, catalog?.lines) || {}))}</p>` : ''}
        <p class="small muted">${esc(trendText(r))} · ${esc(windowLabel)}${r.games < 5 ? ' · small sample' : ''}${r.injuryStatus ? ` · Injury report: ${esc(r.injuryStatus)}` : ''}</p>
        ${historyChart(hist.map(h => Number(h.value)), hist.map(h => String(h.date || '').slice(5)), r.line, dir, { legend: false, titles: hist.map(h => String(h.date || '')) })}
        <p class="small"><a href="#game/${esc(r.gameId)}">${esc(r.matchup || 'Game')} · ${esc(whenShort(r.kickoff))} →</a></p></div>`;
    }).join('')}</div>${rows.length > shown.length ? `<p style="margin-top:12px"><button type="button" class="btn" data-more-trends>Show ${Math.min(40, rows.length - shown.length)} more</button></p>` : ''}`
      : empty('No trends match', 'Try a lower hit rate, another history window or stat, or clear the search. Old and missing prices stay hidden.', 'research');
    const W = { season: 'Season', last10: 'Last 10', last5: 'Last 5' }, K = { main: 'Main lines', alternate: 'Alternates', milestone: 'Milestones' };
    return `<div class="toolbar"><div class="chip-scroll">${seg('trendRate', ['70', '80', '90', '100'].map(r => [r, `${r}${r === '100' ? '%' : '%+'} · ${pass(forRate(r)).length}`]), t.rate)}</div></div>
      ${filtersFold('trends', [W[t.window], K[t.kind], (TREND_STATS.find(([k]) => k === (t.stat || 'all')) || [, 'All stats'])[1], day === 'today' ? 'Today' : '', t.heavy ? '' : 'No heavy favorites'].filter(Boolean).join(' · '),
        `${seg('trendWindow', Object.entries(W), t.window)}${seg('trendKind', Object.entries(K), t.kind)}<label class="sr" for="tstat">Stat</label><select id="tstat" class="select" data-select="trendStat">${TREND_STATS.map(([k, l]) => `<option value="${k}"${(t.stat || 'all') === k ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
        ${route.game || !hasToday ? '' : seg('trendDay', [['all', 'All upcoming'], ['today', 'Today']], day)}
        ${heavyCount || !t.heavy ? `<button type="button" class="chip" data-flag-trend="heavy" aria-pressed="${!t.heavy}">Hide heavy favorites${heavyCount ? ` (${heavyCount})` : ''}</button>` : ''}`)}
      <div class="toolbar"><div class="grow"><label class="sr" for="tq">Search</label><input id="tq" class="search" type="search" placeholder="Player, team or market" value="${esc(state.q)}" data-input="q" autocomplete="off" maxlength="160"></div></div>
      <p class="small muted" style="margin-bottom:10px">${shown.length} of ${rows.length} trend${rows.length === 1 ? '' : 's'} · updated ${esc(ago(data.generatedAt))} · verify prices.${fellBack ? ' No games today, so this shows every upcoming game.' : ''}${route.game ? ' <a href="#research/trends">Show all games →</a>' : ''} Even a 4-of-4 run at −900 needs to win more than 90% of the time to profit. Green cleared the line, red missed, gray tied or not recorded. ${shareLink('trends', route)}</p>${list}`;
  };

  /* Research · Players: the props.cash-style matchup charts (every player in a game, bars vs the line), search and
     defense-vs-position. Same data as the old Charts page (player-charts/<L>.json). */
  const CHART_STATS = [['recYds', 'Rec yds'], ['rec', 'Receptions'], ['targets', 'Targets'], ['rushYds', 'Rush yds'], ['car', 'Carries'],
    ['passYds', 'Pass yds'], ['cmp', 'Completions'], ['att', 'Pass att'], ['passTD', 'Pass TD'], ['rushTD', 'Rush TD'], ['recTD', 'Rec TD'], ['recLong', 'Long rec'], ['rushLong', 'Long rush'], ['kPts', 'Kick pts']];
  const chartHas = (pl, key) => Object.prototype.hasOwnProperty.call(pl.projection || {}, key) || Object.prototype.hasOwnProperty.call(pl.lines || {}, key) || (pl.underReview || []).includes(key)
    || (pl.rows || []).some(r => Object.prototype.hasOwnProperty.call(r.stats || {}, key));
  const matchupCharts = async league => {
    const [data, catalog] = await Promise.all([maybe(`app/player-charts/${league}.json`), lineData(league)]);
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
    const gameById = new Map(games.map(g => [g.id, g]));
    const query = p.q.trim().toLowerCase();
    const nameMatch = pl => {
      if (!query) return true;
      const game = gameById.get(pl.gameId) || {};
      const team = game[pl.side] || {};
      return [pl.name, pl.pos, team.name, team.abbreviation].some(value => String(value || '').toLowerCase().includes(query));
    };
    const pool = (data.players || []).filter(pl => ids.has(pl.gameId) && inPos(pl) && nameMatch(pl));
    const stats = CHART_STATS.filter(([k]) => pool.some(pl => chartHas(pl, k)));
    const DEF_STAT = { QB: 'passYds', RB: 'rushYds', WR: 'recYds', TE: 'recYds', PK: 'kPts' };
    const natural = pos === 'all' || (C.POSITION_STATS[pos === 'PK' ? 'PK' : pos] || []).includes(p.chartStat);
    const key = natural && stats.some(([k]) => k === p.chartStat) ? p.chartStat : ((stats.find(([k]) => k === DEF_STAT[pos]) || stats[0] || [p.chartStat])[0]);
    const hasLine = pl => isNum(((pl.lines || {})[key] || {}).line), anyLine = pool.some(pl => chartHas(pl, key) && hasLine(pl));
    const cards = g => ['away', 'home'].map(side => {
      const team = g[side];
      const list = (data.players || []).filter(pl => pl.gameId === g.id && pl.side === side && chartHas(pl, key) && inPos(pl) && nameMatch(pl));
      list.sort((a, b) => ((b.projection || {})[key] ?? -1) - ((a.projection || {})[key] ?? -1));
      const top = anyLine ? list.filter(hasLine) : list, rest = anyLine ? list.filter(pl => !hasLine(pl)) : [];
      if (!list.length) return '';
      const t = { ...team, abbr: team.abbreviation };
      const card = pl => {
          const rows = C.chartHistory(pl.rows, key, { chartWindow: p.chartWindow });
          const values = rows.map(r => r.stats[key]);
          const cur = (pl.lines || {})[key];
          const line = cur && isNum(cur.line) ? cur.line : null;
          const dir = cur && cur.direction === 'under' ? 'under' : 'over';
          const status = C.quoteStatus(cur, g.kickoff);
          const proj = (pl.projection || {})[key], review = (pl.underReview || []).includes(key);
          const matched = priceMatch({ gameId: g.id, athleteId: pl.id, stat: key, direction: dir, line, odds: cur?.odds, book: cur?.book }, catalog?.lines);
          const gap = averageGap(proj, values);
          return `<a class="card" style="color:inherit;display:block" href="#player/${esc(league)}/${esc(pl.id)}?stat=${esc(key)}"><div class="with-art">${headshot(league, pl.id, 'sm', null, pl.pos)}<div><b>${esc(pl.name)}</b> <span class="muted small">${esc(pl.pos || '')}</span></div></div>
            <p class="small" style="margin:8px 0 4px">${status.current ? 'Line' : 'Reference line'} <b>${line == null ? '–' : esc(C.statValue(line, key))} ${esc(dir)}</b> · Our average <b>${review ? 'Projection under review' : esc(C.statValue(proj, key))}</b> · Hits <b>${line == null ? '–' : `${values.filter(v => C.thresholdResult(v, line, dir) === 'hit').length}/${values.length}`}</b> (${values.length} games)</p>
            <p class="tiny muted">${esc(status.label)}${cur && cur.book ? ` · ${esc(bookLabel(cur.book) || cur.book)}` : ''}${cur && isNum(cur.odds) ? ` ${esc(oddsText(cur.odds))}` : ''}${cur && cur.observedAt ? ` · ${esc(ago(cur.observedAt))}` : ''}</p>
            <p class="small">${esc(researchPrice(matched || {}))}</p>${gap ? `<p class="small red">${esc(gap)}</p>` : ''}
            ${matched?.qbNews ? `<p class=caution>QB news: ${esc(matched.qbNews)}</p>` : ''}
            ${historyChart(values, rows.map(r => String(r.date).slice(5)), line, dir, { legend: false })}</a>`;
        };
      return `<div style="margin-top:10px"><div class="with-art" style="margin-bottom:8px">${teamMark(t, 'sm', league)}<b>${esc(team.name)}</b><span class="muted small">${list.length} player${list.length === 1 ? '' : 's'}</span></div>
        <div class="grid two">${top.map(card).join('')}</div>${rest.length ? `<details class="plain-fold" data-box="nl:${esc(g.id)}:${side}:${key}"><summary>${rest.length} more without a line</summary><div class="grid two">${rest.map(card).join('')}</div></details>` : ''}</div>`;
    }).join('');
    const blocks = chosen.map(g => [g, cards(g)]).filter(([, h]) => h);
    const gameOptions = `<option value="next"${p.game === 'next' ? ' selected' : ''}>Next slate · ${esc(dayLabel(games[0].kickoff))}</option><option value="all"${p.game === 'all' ? ' selected' : ''}>All upcoming · ${games.length} games</option>${days.slice(1).map(d => { const g0 = games.find(g => g.day === d); return `<option value="day:${esc(d)}"${p.game === 'day:' + d ? ' selected' : ''}>${esc(dayLabel(g0.kickoff))}</option>`; }).join('')}${games.map(g => `<option value="${esc(g.id)}"${p.game === g.id ? ' selected' : ''}>${esc(g.away.abbreviation)} at ${esc(g.home.abbreviation)} · ${esc(whenShort(g.kickoff))}</option>`).join('')}`;
    return `<div class="toolbar"><div class="grow"><label class="sr" for="cq">Find a player</label><input id="cq" class="search" type="search" placeholder="Find a player or team" value="${esc(p.q)}" data-input="pq" autocomplete="off" maxlength="160"></div>
        <label class="sr" for="cstat">Stat</label><select id="cstat" class="select" data-select="chartStat">${(stats.length ? stats : CHART_STATS).map(([k, l]) => `<option value="${k}"${k === key ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>
        <label class="sr" for="cgame">Games</label><select id="cgame" class="select" data-select="chartGame">${gameOptions}</select>
</div>${filtersFold('players', `${pos === 'all' ? 'All positions' : pos === 'PK' ? 'K' : pos} · ${{ last5: 'Last 5', last10: 'Last 10', season: 'Season' }[p.chartWindow]}`, seg('cpos', [['all', 'All'], ['QB', 'QB'], ['RB', 'RB'], ['WR', 'WR'], ['TE', 'TE'], ['PK', 'K']], pos) + seg('cwin', [['season', 'Season'], ['last10', 'Last 10'], ['last5', 'Last 5']], p.chartWindow))}
      ${note ? `<p class="small" style="margin-bottom:6px">${esc(note)}</p>` : ''}<p class="small muted" style="margin-bottom:6px">${anyLine ? '' : `No recorded lines for ${esc((CHART_STATS.find(([k]) => k === key) || [, key])[1])}. Showing history only. `}Every player in the matchup with recent games against the line we saw. Green cleared the line, red missed, gray tied or not recorded. History is not a probability. ${shareLink('players')}</p>
      ${blocks.length ? blocks.map(([g, h]) => `<section class="section" style="margin:14px 0"><div class="section-head"><h2>${esc(g.away.abbreviation)} at ${esc(g.home.abbreviation)}</h2><a class="more" href="#game/${esc(g.id)}">Game page →</a></div><p class="section-note">${esc(when(g.kickoff))}</p>${h}</section>`).join('') : empty('No players match', 'Try another name, team, stat or position.', 'research')}`;
  };

  const DEFENSE_STATS = { QB: ['passYds', 'passTD', 'att', 'cmp', 'int', 'sacks', 'rushYds'], RB: ['rushYds', 'car', 'rushTD', 'recYds', 'rec', 'targets'],
    WR: ['recYds', 'rec', 'targets', 'recTD'], TE: ['recYds', 'rec', 'targets', 'recTD'] };
  const researchPlayers = async route => {
    const p = state.players, league = state.league === 'ALL' ? p.league : state.league === 'CFB' ? 'CFB' : 'NFL';
    /* Real links, so Back, refresh and sharing work. Teams stays reachable from old links. */
    const subTabs = `<div class="chip-scroll">${segLinks([['#research/players', 'Matchups', 'matchup'], ['#research/players?view=search', 'Search', 'search'], ['#research/players?view=defense', 'Defenses', 'defense']], p.sub === 'teams' ? 'defense' : p.sub)}</div>`;
    const intro = state.league === 'ALL' ? `<div class="toolbar">${seg('plg', [['NFL', 'NFL'], ['CFB', 'College']], league)}</div>` : '';
    if (p.sub === 'matchup') return `<div class="toolbar">${subTabs}</div>${intro}${await matchupCharts(league)}`;
    const [index, teams] = await Promise.all([get(`app/players/${league}.json`), teamDirectory(league)]);
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
      ${section('Notes', notes.length ? notes.map(n => `<div class="card" style="margin-bottom:10px"><p class="eyebrow">${esc(LEAGUE_NAME[n.league] || n.league)} · ${esc(when(n.publishedAt))}</p>
          ${(n.takeaways || []).length ? `<ul class="fa" style="margin-top:6px">${n.takeaways.map(t => `<li class="for">${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${(n.weeklyReview || []).length ? `<p class="eyebrow" style="margin-top:10px">Review</p><ul class="fa">${n.weeklyReview.map(t => `<li>${esc(text(t))}</li>`).join('')}</ul>` : ''}
          ${(n.watch || []).length ? `<p class="eyebrow" style="margin-top:10px">Watching</p><ul class="fa">${n.watch.map(w => `<li><b>${esc(w.title)}</b>${w.gameId ? ` (<a href="#game/${esc(w.gameId)}">${esc(gameName(w.gameId))}</a>)` : ''}: ${esc(w.why || '')}${w.needs ? ` <span class="muted">Needs: ${esc(Array.isArray(w.needs) ? w.needs.join('; ') : w.needs)}</span>` : ''}</li>`).join('')}</ul>` : ''}</div>`).join('')
        : '<p class="muted small">No notes right now.</p>')}`;
  };

  /* ---------- Games ---------- */
  /* The projection card kept from the old site, front and center: projected score, total, team strength
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
    const lines = hasScore || g.fcs || !isNum(v2.margin) ? '' : `<div class="pc-lines"><span class="h"></span><span class="h">Mine</span><span class="h">Market</span><span class="h">${esc(opts.sideLabel || 'My side')}</span>
      <span class="k">Spread</span><span class="num">${esc(C.modelSpread(g.home.abbr, g.away.abbr, v2.margin))}</span><span class="num">${esc(favSpread(g.home.abbr, g.away.abbr, m.spread))}</span><span>${lean.side ? ourSide(`${sideTeam.abbr}${sideLine}`, lean.side.chance, raw.spreadCaution) : '<span class="muted">No lean</span>'}</span>
      <span class="k">Total</span><span class="num">${esc(C.fixed(v2.total, 1))}</span><span class="num">${esc(C.fixed(m.total, 1))}</span><span>${lean.total ? ourSide(`${lean.total.direction} ${m.total ?? ''}`, lean.total.chance, raw.totalCaution) : '<span class="muted">No lean</span>'}</span></div>`;
    const gap = gapScore(g);
    /* No generic caution (owner, Oct 7): a specific, data-supplied reason arrives through opts.extra when one applies. */
    const note = g.fcs ? 'FBS vs FCS: my number is not reliable here.' : hasScore ? '' : v2.sparse ? 'Thin history: a team has fewer than three games, so this leans on last season.' : '';
    const linked = opts.link !== false;
    return `<div class="proj${opts.big ? ' big' : ''}${live ? ' live' : ''}">${linked ? `<a class="proj-link" href="#game/${esc(g.id)}">` : '<div class="proj-link">'}
      <div class="pc-meta"><span>${live ? '<span class="live-dot"></span>' : ''}${esc(g.statusWord ? `${g.statusWord} · was ${whenShort(g.kickoff)}` : final ? `${/OT/.test(g.status || '') ? g.status : 'Final'} · ${whenShort(g.kickoff).split(',')[0]}` : live ? (g.status || 'Live') : whenShort(g.kickoff))} · ${esc(g.league === 'CFB' ? 'College' : g.league)}${g.neutral ? ' · neutral site' : ''}</span>${opts.badge || (!hasScore && gap >= 80 ? `<span class="gap-chip big" title="Bigger gap than ${gap}% of stored games">Unusual gap vs market</span>` : '')}</div>
      <div class="pc-top">${team(g.away)}<div class="pc-mid"><small>${label}</small><b class="num">${score}</b><span>${esc(sub)}</span></div>${team(g.home)}</div>
      ${bar}${lines}${note ? `<p class="caution">${esc(note)}</p>` : ''}${linked ? '</a>' : '</div>'}${hasScore ? '' : opts.extra || ''}</div>`;
  };


  /* ---------- Record ---------- */
  const clvWords = clv => !isNum(clv) ? '' : clv > 0 ? `line moved our way by ${C.fixed(clv, 1)}` : clv < 0 ? `line moved against us by ${C.fixed(Math.abs(clv), 1)}` : 'closed at our number';
  const receipt = (p, clvById) => {
    const vm = pickVM(p);
    const mark = p.result === 'win' ? ['hit', '✓', 'Hit'] : p.result === 'loss' ? ['miss', '✗', 'Miss'] : p.result === 'push' ? ['push', '–', 'Push'] : p.result === 'void' ? ['push', '–', 'Void'] : ['open', '•', 'Pending'];
    const u = C.unitsFor(p);
    const assumed = Boolean(p.priceAssumed || C.isUnpricedImport(p));
    const clv = clvById.get(p.id);
    const price = p.odds == null ? 'no price recorded' : assumed ? `${oddsText(p.odds)} assumed · no price recorded` : `${oddsText(p.odds)} ${/^espn ?bet$/i.test(String(p.book || '').trim()) ? 'ESPN BET' : bookLabel(p.book) || ''}`;
    const actual = p.resultDetail ? `${p.player || niceTitle(p.title || '').split(/\s+(?:OVER|UNDER)\s+/i)[0]} · ${p.resultDetail}` : p.actual != null ? String(typeof p.actual === 'object' ? Object.entries(p.actual).map(([k, v]) => `${k} ${v}`).join(', ') : p.actual).split(/[.;]\s/)[0] : '';
    const meta = [price, whenShort(p.kickoff || p.publishedAt), p.featured ? 'Pick of the Day' : '', clvWords(clv), actual ? `result ${actual}` : '', p.earlyExit ? 'early-exit credit (counts −1u in the headline)' : ''].filter(Boolean).join(' · ');
    const right = p.result ? (u == null ? '' : assumed ? `<span class="u muted" title="${esc(p.priceNote || 'No price was recorded, so this counts at an assumed −115.')}">(${esc(units(u))})</span>` : `<span class="u ${u > 0 ? 'green' : u < 0 ? 'red' : 'muted'}">${esc(units(u))}</span>`)
      : '<span class="u muted small">Pending</span>';
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
      ${upcoming.length ? `<div class="receipts" style="margin-top:8px">${upcoming.slice(0, 8).map(r => `<div class="receipt" style="grid-template-columns:minmax(0,1fr)"><div><b>${esc(r.away)} at ${esc(r.home)}</b><span>Projected total ${esc(r.projection)} · saved line ${esc(r.line)} · ${esc(whenShort(r.kickoff))} · price checked ${esc(whenShort(r.capturedAt))}${r.sparse ? ' · thin history' : ''}</span></div></div>`).join('')}</div>` : ''}
      ${seasons.length ? `<details class="more-box" data-box="trial-history:${esc(lg)}" style="margin-top:8px"><summary>Season history</summary><div class="table-wrap"><table class="t"><tbody>${seasons.map(row => `<tr><td>${esc(row.season)} · ${row.phase === 'playoffs' ? 'Playoffs' : row.phase === 'regular' ? 'Regular season' : 'Stage not recorded'}</td><td class="n">${trial ? `${esc(row.recorded)} saved` : `${esc(row.gamesQuoted || 0)} quoted in this stage`}</td><td class="n">${trial ? (() => { const r = row.record || {}; const n = (r.win || 0) + (r.loss || 0) + (r.push || 0); return n ? `${r.win || 0}–${r.loss || 0}${r.push ? '–' + r.push : ''}` : 'Pending'; })() : `${esc(row.gamesGraded || 0)} finals`}</td></tr>`).join('')}</tbody></table></div>${trial ? '' : '<p class="small muted" style="margin-top:6px">A game recorded in more than one stage is counted in each.</p>'}</details>` : ''}
      <p class="small" style="margin-top:8px"><a href="#games/live?sport=${esc(lg)}">Live scores →</a></p></div>`;
  };
  /* My ticket: legs are re-checked against the current board every time, so a gone or moved price is never priced. */
  const ticketRows = async () => {
    const data = await lineData('ALL');
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
      <p class="small" style="margin-top:8px">${r.arb ? `${money(r.profit)} remains if either side wins and both bets are accepted and settled as expected.` : `At these two prices, the required win rates add up to ${Number(r.implied).toFixed(2)}%. They must add up to less than 100% for a locked return.`}</p></div>`;
  };

  /* ---------- Lazy bundles ---------- */
  /* Record, More, player and Games pages are not part of the first paint. Each bundle is one fingerprinted file. */
  const MORE_VIEW_NAMES = ['player', 'record', 'vegas', 'more', 'glossary', 'start', 'saved', 'ticket', 'arbs', 'lab',
    'schedule', 'status', 'feedback'];
  const GAMES_VIEW_NAMES = ['games', 'game', 'team'];
  const MORE_ASSET = 'app-more.js?v=sha256-cb077e3df99d';
  const GAMES_ASSET = 'app-games.js?v=sha256-e62c5f5559e3';
  const moreContext = (overrides = {}) => ({ C, P, L, state, esc, head, section, empty, seg, segLinks, FOOTBALL, LEAGUE_NAME,
    teamDirectory, maybe, get, indexGames, withLive, defenseRows, projCard, teamMark, headshot, when, whenShort,
    dayLabel, bookLabel, ago, niceTitle, allPicks, lineData, saved, oddsText, units, wl, roiOf, rate, trialCard, receipt, climbRow, cumulativeUnits, OWNER_FLAGS, kpiStrip, clvSummary, ticketRows, ticketSummary, arbFor, arbSummary, officialKey, isNum, inLeague, pickVM, meter,
    GAMES, HEADSHOT, MARK, STAT_UNITS, clock, defGames, defenseVerdict, disc, filtersFold, hasValue, lineVM, logoImg, minus, nameSize, odd, onBoard, panelVars, pctOne, teamPanel, ticketWhen, toneFor, watchButton, HOUSE, rail, holdOf, heldWords, slip, etDay, ...overrides });
  const gamesContext = (overrides = {}) => moreContext({ setLeague, liveStamp, liveFor, LIVE, gapScore, STAT_WORD, favSpread, marketLabel, quoteAge, round1, fairAmerican,
    boardRow, matchupSignals, researchPrice, pctText, currentUpset, upsetRow, heavyFavorite, trendText, historyChart, ticket, luminance, ...overrides });
  const BUNDLES = { more: { asset: MORE_ASSET, global: 'KRMore', context: moreContext, word: 'More pages' },
    games: { asset: GAMES_ASSET, global: 'KRGames', context: gamesContext, word: 'Games pages' } };
  const ensureBundle = key => {
    const b = BUNDLES[key];
    if (b.views) return Promise.resolve(b.views);
    if (b.loading) return b.loading;
    b.loading = new Promise((resolveViews, rejectViews) => {
      let script = null;
      /* A failed tag leaves <head>, so a retry adds one live script, not a second dead one. */
      const fail = error => {
        b.loading = null;
        if (script && script.remove) script.remove();
        rejectViews(error instanceof Error ? error : new Error(error && error.message ? error.message : `${b.word} did not load`));
      };
      const finish = () => {
        try {
          if (typeof window[b.global] !== 'function') throw new Error(`${b.word} did not load`);
          const views = window[b.global](b.context());
          if (!views || typeof views !== 'object') throw new Error(`${b.word} did not load`);
          b.views = views;
          resolveViews(views);
        } catch (error) {
          fail(error);
        }
      };
      if (typeof window[b.global] === 'function') { finish(); return; }
      script = document.createElement('script');
      script.src = b.asset; script.async = true;
      script.onload = finish;
      script.onerror = () => fail(new Error(`${b.word} did not load`));
      document.head.appendChild(script);
    });
    return b.loading;
  };
  const ensureMore = () => ensureBundle('more'), ensureGames = () => ensureBundle('games');
  MORE_VIEW_NAMES.forEach(name => { VIEWS[name] = async route => (await ensureMore())[name](route); });
  GAMES_VIEW_NAMES.forEach(name => { VIEWS[name] = async route => (await ensureGames())[name](route); });
  /* Games data does not wait for its bundle either. */
  VIEWS.games = async route => { if (route.tab !== 'live') get('app/today.json').catch(() => null); return (await ensureGames()).games(route); };
  VIEWS.game = async route => { if (route.id) get(`app/games/${route.id}.json`).catch(() => null); return (await ensureGames()).game(route); };
  /* The player page's data does not wait for the lazy bundle: start the same cached requests it makes, in parallel. */
  VIEWS.player = async route => {
    if (route && FOOTBALL.includes(route.league) && route.id) {
      const quiet = x => x && x.catch ? x.catch(() => null) : x;
      quiet(get(`app/players/${route.league}.json`).then(index => get(`app/players/${route.league}/${C.shardOf(route.id, index.shards)}.json`)));
      [teamDirectory(route.league), get('app/today.json'), lineData(route.league)].forEach(quiet);
    }
    return (await ensureMore()).player(route);
  };

  /* =====================================================================
     ROUTER AND EVENTS
     ===================================================================== */

  let lastHash = null;
  const chrome = route => {
    const active = TAB_OF[route.view] || 'today';
    const tabHref = key => key === 'research' ? '#research/lines' : `#${key}`;
    /* Text-only tabs (Kitchen Ticket): the same links in the phone tab bar and the desktop header. */
    const links = TABS.map(([key, label]) => `<a href="${tabHref(key)}" ${key === active ? 'aria-current="page"' : ''}>${esc(label)}</a>`).join('');
    $('#tabbar').innerHTML = links;
    $('#top-tabs').innerHTML = links;
    const sel = $('#league');
    if (!sel.options.length) { const opt = k => `<option value="${k}">${esc(LEAGUE_NAME[k])}</option>`;
      sel.innerHTML = `${opt('ALL')}<optgroup label="Best bets and research">${FOOTBALL.map(opt).join('')}</optgroup><optgroup label="Scores and trials">${Object.keys(LEAGUE_NAME).filter(k => k !== 'ALL' && !FOOTBALL.includes(k)).map(opt).join('')}</optgroup>`; }
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
    propHistory(d.league, d.athlete, d.stat, Number(d.line), d.dir, d.game, d.before || null, null, d.held === '1').then(html => { box.innerHTML = html; }).catch(() => { box.innerHTML = '<p class="small muted">History unavailable right now.</p>'; });
  };
  /* A newer render always wins: a slow fetch from an older one never paints over it. */
  let renderToken = 0, rendering = false;
  /* Folds the reader opened or closed this visit. */
  const boxMemory = new Map();
  async function render(soft = false) {
    const token = ++renderToken;
    const savedY = (history.state || {}).scroll;
    rendering = true;
    let route = resolve(location.hash);
    if (route.legacy && route.league) setLeague(route.league);
    if (route.legacy && route.ctx) applyContext(route);
    const next = canonical(route);
    if (next && next !== location.hash) { try { history.replaceState(null, '', next); } catch (_) { /* rate limited */ } route = resolve(next); }
    /* The bare Today tab is the whole football day. A sport-specific Today remains an explicit URL choice. */
    if (route.view === 'today' && location.hash !== appliedHash) { appliedHash = location.hash; setLeague(route.league || 'ALL'); }
    chrome(route);
    const view = $('#view');
    const focusKey = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.input : null;
    const caret = focusKey ? document.activeElement.selectionStart : null;
    /* Keep keyboard focus on the control that was used, and keep open dropdowns open, across a soft re-render. */
    const ae = document.activeElement;
    const focusSel = soft && ae && ae !== document.body && !focusKey ? (ae.id ? `#${CSS.escape(ae.id)}` : ['set', 'flagTrend', 'select', 'watch', 'watchPick', 'addLine', 'accept', 'removeLeg'].map(k => ae.dataset && ae.dataset[k] != null ? `[data-${k.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}="${CSS.escape(ae.dataset[k])}"]` : null).find(Boolean)) : null;
    const openRows = [...document.querySelectorAll('details[open][data-row]')].map(d => d.dataset.row);
    const sideScroll = soft ? [...document.querySelectorAll('#view .chart-wrap, #view .table-wrap, #view .chip-scroll')].map(e => e.scrollLeft) : [];
    const boxes = soft ? new Map([...document.querySelectorAll('details[data-box]')].map(d => [d.dataset.box, d.open])) : new Map();
    const openBoxes = soft ? [...document.querySelectorAll('details[open]:not([data-row]):not([data-box]) > summary')].map(x => x.textContent.trim()) : [];
    /* A painted Today hero stays while Today loads; any other page gets the placeholder, never Today's hero. */
    const slow = soft ? null : setTimeout(() => { if (token === renderToken && !(route.view === 'today' && view.querySelector('.hero-first'))) view.innerHTML = LOADING; }, 150);
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
    for (const d of document.querySelectorAll('details[data-box]')) if (boxes.has(d.dataset.box)) d.open = boxes.get(d.dataset.box); else if (boxMemory.has(d.dataset.box)) d.open = boxMemory.get(d.dataset.box);
    if (openBoxes.length) for (const sum of document.querySelectorAll('details:not([data-row]):not([data-box]) > summary')) { if (openBoxes.includes(sum.textContent.trim())) sum.parentElement.open = true; }
    const h1 = view.querySelector('h1');
    document.title = `${h1 ? h1.textContent : 'Kook\'n'} · Kook'n`;
    if (navigated) { window.scrollTo(0, isNum(savedY) ? savedY : 0); if (h1) { h1.setAttribute('tabindex', '-1'); h1.focus({ preventScroll: true }); } }
    const target = navigated && route.anchor ? document.getElementById(route.anchor) : null;
    if (target) { target.scrollIntoView({ block: 'start' }); target.setAttribute('tabindex', '-1'); target.focus({ preventScroll: true }); }
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
    if (route.view === 'today') return state.league === 'ALL' ? '#today' : `#today?sport=${state.league}`;
    if (route.view === 'research' && (route.league || route.game)) return `#research/${route.mode}`;
    if (route.view === 'vegas' && route.league) return '#vegas';
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
      /* A missing ESPN cutout: the ticket or player hero shows the team's logo disc instead (SPEC 5.3), no breakout. */
      if (img instanceof HTMLImageElement && img.closest('.kt-ph')) { const order = img.closest('.kt-order'); if (order) order.classList.add('no-photo'); }
      if (img instanceof HTMLImageElement && img.closest('.kt-face, .kt-disc, .kt-logo')) img.remove();
    }, true);
    window.addEventListener('hashchange', () => { appliedHash = null; state.player.hash = null; render(); });
    const warm = event => { const a = event.target.closest && event.target.closest('a[href^="#game"], a[href^="#team/"]'); if (a) ensureGames().catch(() => {}); };
    ['pointerover', 'focusin', 'touchstart'].forEach(type => document.addEventListener(type, warm, { passive: true }));
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
          type: v => { state.board.type = v; state.board.limit = 40; saveBoard(); }, show: v => { state.board.show = v === 'all' ? 'all' : 'value'; state.board.limit = 40; saveBoard(); }, trendRate: v => { state.trends.rate = v; }, trendWindow: v => { state.trends.window = v; }, trendKind: v => { state.trends.kind = v; }, trendDay: v => { state.trends.day = v; },
          pos: v => { state.players.pos = v; }, plg: v => { state.players.league = v === 'CFB' ? 'CFB' : 'NFL'; state.players.game = 'next'; state.players.q = ''; }, cpos: v => { state.players.chartPos = v; }, cwin: v => { state.players.chartWindow = v; },
          dstat: v => { state.players.stat = v; }, dscope: v => { state.players.scope = v; }, dorder: v => { state.players.order = v; },
          gnav: v => { const [k, x] = v.split('='); state.games.nav[k] = k === 'close' ? !state.games.nav.close : x; state.games.all = false; },
          rcal: v => { const [k, x] = v.split('='); state.record.cal[k] = k === 'day' && state.record.cal.day === x ? null : x; if (k !== 'day') state.record.cal.day = null; },
          gsort: v => { state.games.sort = v; state.games.all = false; }, gday: v => { state.games.day = v; }, gup: v => { state.games.upDay = v; state.games.all = false; }, gstatus: v => { state.games.status = v; },
          pstat: v => { state.player.stat = v; }, pwin: v => { state.player.window = v; }, pseason: v => { state.player.season = v; }, stakeMode: v => { state.stake.mode = v; saved.set('stake', state.stake); },
        };
        if (SETTERS[key]) SETTERS[key](value);
        if (['trendRate', 'trendWindow', 'trendKind', 'trendDay', 'cpos', 'cwin'].includes(key)) { state.trends.limit = 40; savePrefs(); }
        render(true); return;
      }
      if (d.flagTrend) { state.trends.heavy = !state.trends.heavy; state.trends.limit = 40; render(true); return; }
      if ('moreRows' in d) { state.board.limit += 40; render(true); return; }
      if ('moreTrends' in d) { state.trends.limit = (state.trends.limit || 40) + 40; render(true); return; }
      if ('allGames' in d) { state.games.all = true; render(true); return; }
      if ('clearQ' in d) { state.q = ''; render(true); return; }
      if ('retry' in d) { cache.clear(); missing.clear(); todayExtras = null; todayExtrasAt = 0; if (liveCache.rows) liveCache.rows.clear(); render(); return; }
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
        const lines = await lineData('ALL');
        const row = ((lines || {}).lines || []).find(r => r.id === d.addLine);
        if (!row) { toast('This price is no longer on the board'); return; }
        state.ticket.push(ticketLeg(row)); saved.set('ticket', state.ticket); toast('Added to your ticket'); render(true);
        return;
      }
      if (d.accept) {
        const lines = await lineData('ALL');
        const row = ((lines || {}).lines || []).find(r => r.id === d.accept);
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
        if (out) out.innerHTML = `<label class="sr" for="fb-text">Your message</label><textarea id="fb-text" class="search" rows="6" readonly>${esc(text)}</textarea><div class="btn-row" style="margin-top:8px"><button type="button" class="btn primary" data-copy-feedback>Copy message</button><a class="btn" href="https://discord.gg/ZnjubjsBPM" target="_blank" rel="noopener">Open Discord ↗</a></div>`;
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
      if (el.matches && el.matches('details[data-box="today-more"]') && !rendering) boxMemory.set('today-more', el.open);
      if (!el.matches || !el.open) return;
      if (el.matches('details[data-row]')) loadRowDetail(el);
    }, true);
    document.addEventListener('input', event => {
      const el = event.target;
      if (el.dataset.input) {
        clearTimeout(inputTimer);
        const SET = { q: v => { state.q = v; state.board.limit = 40; state.trends.limit = 40; }, pq: v => { state.players.q = v; }, gq: v => { state.games.q = v; }, rq: v => { state.record.q = v; } };
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
      const SELECTS = { gconf: v => { state.games.nav.conf = v; state.games.all = false; }, sort: v => { state.board.sort = v; state.board.limit = 40; saveBoard(); }, season: v => { state.record.season = v; }, phase: v => { state.record.phase = v; },
        chartStat: v => { state.players.chartStat = v; }, trendStat: v => { state.trends.stat = v; }, chartGame: v => { state.players.game = v; }, playerSeason: v => { state.player.season = v; }, defStat: v => { state.players.stat = v; } };
      if (el.dataset.select && SELECTS[el.dataset.select]) { SELECTS[el.dataset.select](el.value); if (['chartStat', 'trendStat'].includes(el.dataset.select)) savePrefs(); render(true); }
    });
    setInterval(refreshPage, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshPage(); });
    render();
  }

  return { model, boot, moreContext, gamesContext, ensureMore, ensureGames, firstPaint, render, views: VIEWS };
});
