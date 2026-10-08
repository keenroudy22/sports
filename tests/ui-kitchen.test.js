'use strict';
/* Kitchen Ticket website (OWNER-DECISIONS 2026-10-07 item 22): the pure model the ticket uses, the team panel port and
   the player page's Under review state. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../site/core.js');
globalThis.KRCore = C;
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');

test('teamPanel matches ticket_kit.team_panel for every stored NFL and college colour pair', () => {
  const fixture = JSON.parse(fs.readFileSync('tests/fixtures/team-panels.json', 'utf8'));
  const college = JSON.parse(fs.readFileSync('data/team-colors-cfb.json', 'utf8')).teams;
  const norm = c => { const v = String(c || '').trim().toLowerCase().replace('#', ''); return v.length === 6 ? '#' + v : ''; };
  const pairs = new Set([...Object.values(college).map(t => `${norm(t.color)}|${norm(t.alternateColor)}`),
    ...Object.values(fixture.nfl).map(([c, a]) => `${norm(c)}|${norm(a)}`)]);
  assert.ok(pairs.size > 300);
  for (const key of pairs) {
    const [primary, alternate] = key.split('|');
    assert.deepEqual(M.teamPanel(primary || null, alternate || null).map(c => c.toUpperCase()), fixture.panels[key].map(c => c.toUpperCase()), key);
  }
  assert.deepEqual(M.teamPanel('#cc0033').map(c => c.toUpperCase()).slice(0, 1), ['#9F0028'], 'Arizona red darkens x0.78');
  assert.equal(M.teamPanel('#c3993f', '#091f3f')[0].toUpperCase(), '#091F3F', 'FIU gold is a banned hue: navy');
});

test('the bet line, unit and name come from the pick fields', () => {
  assert.deepEqual(M.betParts({ displayTitle: 'TK King OVER 49.5 receiving yards', athleteId: '1', market: 'recYds', direction: 'over', line: 49.5 }),
    { kind: 'prop', name: 'TK King', bet: 'OVER 49.5', unit: ['REC', 'YDS'] });
  assert.deepEqual(M.betParts({ displayTitle: 'Arizona at West Virginia under 61', marketType: 'total', direction: 'under', line: 61 }).bet, 'UNDER 61');
  const spread = M.betParts({ displayTitle: 'Texas A&M -16.5 vs Kentucky', marketType: 'spread', direction: 'home', line: -16.5 },
    { home: { abbr: 'TA&M' }, away: { abbr: 'UK' } });
  assert.equal(spread.bet, 'TA&M −16.5');
  assert.deepEqual(M.betParts({ displayTitle: 'Old Player OVER 50.5 receiving yards', kind: 'props', marketType: 'total' }).bet, 'OVER 50.5', 'old rows without athleteId');
  assert.ok(M.betSize(M.betParts({ displayTitle: 'X UNDER 179.5 passing yards', athleteId: '1', market: 'passYds', direction: 'under', line: 179.5 })) < 68);
  assert.equal(M.nameSize('TK King'), 46);
  assert.ok(M.nameSize('Marcellous Hawkins Jr.') <= 27, 'long names drop to two lines at most');
});

test("the chef's lines are count-aware and use the build's last game day", () => {
  const night = { kickoff: '2026-10-07T23:30:00Z' }, noon = { kickoff: '2026-10-10T16:00:00Z' };
  assert.equal(M.ledeTitle([night], true), 'One for tonight.');
  assert.equal(M.ledeTitle([noon, night, night], true), 'Three for today.');
  assert.equal(M.ledeTitle([{ kickoff: '2026-10-13T00:15:00Z' }], false), 'One for Monday.');
  assert.equal(M.ledeTitle([], true), 'Nothing on the rail yet.');
  assert.equal(M.dateLine('2026-10-07T20:00:00Z', { day: '2026-10-05', wins: 0, losses: 1, pushes: 0 }), 'Wednesday, Oct 7. Monday went 0-1.');
  assert.equal(M.dateLine('2026-10-07T20:00:00Z', null), 'Wednesday, Oct 7.');
  assert.match(M.dateLine('2026-10-20T20:00:00Z', { day: '2026-10-05', wins: 2, losses: 1, pushes: 1 }), /Monday, Oct 5 went 2-1-1\.$/);
});

test('a settled slip prints the margin only when it agrees with the graded result', () => {
  const total = { marketType: 'total', direction: 'under', line: 48, result: 'loss', actual: 'Falcons 45, Saints 24' };
  assert.equal(M.resultLine(total), 'Final 45-24, missed by 21.');
  assert.equal(M.resultLine({ athleteId: '1', direction: 'over', line: 45.5, result: 'loss', actual: 'Marcellous Hawkins Jr.: 32 rushing yards' }), 'Had 32, missed by 13.5.');
  assert.equal(M.resultLine({ ...total, result: 'win' }), 'Final 45-24.', 'a book settlement that differs from the box score gets no margin');
  assert.equal(M.resultLine({ marketType: 'spread', direction: 'home', line: -3, result: 'win', actual: 'A 20, B 10' }), 'Final 20-10.');
  assert.equal(M.resultLine({ result: 'win' }), '');
});

/* The player page runs from the lazy bundle; load both files in one browser-shaped sandbox. */
const KEYS = ['cmp', 'att', 'passYds', 'passTD', 'int', 'sacks', 'car', 'rushYds', 'rushTD', 'rushLong', 'targets', 'rec', 'recYds', 'recTD', 'recLong',
  'rzTgt', 'i10Tgt', 'rzCar', 'i10Car', 'i5Car', 'scrambles', 'fumLost', 'fgm', 'fga', 'xpm', 'kPts', 'snaps', 'snapPct'];
const row = (event, date, opp, home, stats) => [event, date, 2026, 1, 2, '2229', opp, home, ...KEYS.map(k => stats[k] ?? null)];
const playerFiles = (held = true) => {
  const athlete = '4870883', game = { id: 'CFB-1', league: 'CFB', kickoff: '2026-10-07T23:30:00Z', state: 'pre', season: 2026, completed: false,
    market: { spread: -6.5 }, home: { id: '2229', abbr: 'FIU', name: 'FIU', color: '#091f3f', alt: '#c3993f' }, away: { id: '166', abbr: 'NMSU', name: 'New Mexico St', color: '#7e141b', alt: '#231f20' } };
  const line = side => ({ id: `l-${side}`, gameId: 'CFB-1', athleteId: athlete, stat: 'passYds', market: 'passing yards', title: `JJ Kohl ${side} 261.5 passing yards`,
    direction: side, line: 261.5, odds: -114, book: 'FanDuel', state: 'open', observedAt: '2026-10-07T17:37:00Z', kickoff: game.kickoff,
    grade: held ? null : { chance: 0.57, needs: 0.533, edge: 3.7, calibrated: true, view: 'lean', projection: 270.1 },
    ...(held && side === 'over' ? { roleSuspect: true, roleHold: 'workload', recentFull: [50, 36, 43], recentVolume: 'att', gradeNote: 'Projection under review' } : {}) });
  return {
    'data/app/players/CFB.json': { keys: KEYS, shards: 128, season: 2026, players: [[athlete, 'JJ Kohl', 'QB', '2229', 'FIU', '2026-09-26', 4]] },
    [`data/app/players/CFB/${Number(athlete) % 128}.json`]: { keys: KEYS, players: { [athlete]: { name: 'JJ Kohl', pos: 'QB', rows: [
      row('e1', '2026-09-05', '58', 0, { cmp: 31, att: 50, passYds: 301, passTD: 1, int: 2 }), row('e2', '2026-09-12', '2084', 1, { cmp: 21, att: 36, passYds: 367, passTD: 3, int: 0 }),
      row('e3', '2026-09-19', '2226', 0, { cmp: 22, att: 43, passYds: 262, passTD: 0, int: 3 }), row('e4', '2026-09-26', '2341', 1, { cmp: 6, att: 11, passYds: 135, passTD: 1, int: 1 })] } } },
    'data/app/teams/CFB.json': { teams: { 2229: { abbr: 'FIU', name: 'FIU', color: '#091f3f', fbs: true }, 166: { abbr: 'NMSU', name: 'New Mexico St', fbs: true } }, defense: { rows: {} } },
    'data/app/today.json': { games: [game], picks: [] },
    'data/app/lines.json': { files: { NFL: 'lines-NFL.json', CFB: 'lines-CFB.json' } },
    'data/app/lines-CFB.json': { league: 'CFB', lines: [line('over'), line('under')] },
    'data/app/games/CFB-1.json': { forecast: { players: { home: { players: [{ id: athlete, att: [23.7, 15, 32], passYds: [167.1, 110, 230], ...(held ? { underReview: ['att', 'passYds', 'cmp'] } : {}) }] } } } },
  };
};
const playerPage = async (held, change = null) => {
  const files = playerFiles(held);
  if (change) change(files);
  const el = () => ({ innerHTML: '', options: [], value: '', dataset: {}, classList: { toggle() {}, add() {}, remove() {} }, querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, focus() {} });
  class FixedDate extends Date { constructor(...a) { super(...(a.length ? a : [Date.parse('2026-10-07T18:00:00Z')])); } static now() { return Date.parse('2026-10-07T18:00:00Z'); } }
  const sandbox = { module: { exports: {} }, exports: {}, KRCore: C, KRLive: require('../site/live.js'), KRPersonal: require('../site/personal.js'),
    location: { hash: '#player/CFB/4870883', origin: 'http://localhost', pathname: '/' }, history: { state: null, replaceState() {} },
    document: { hidden: true, body: el(), activeElement: null, querySelector: () => el(), querySelectorAll: () => [], createElement: el, head: { appendChild() {} }, addEventListener() {} },
    localStorage: { getItem: () => null, setItem: () => {} }, matchMedia: () => ({ matches: false }),
    fetch: async url => files[url] ? { ok: true, json: async () => JSON.parse(JSON.stringify(files[url])) } : { ok: false, status: 404, json: async () => ({}) },
    console, URL, URLSearchParams, Intl, Date: FixedDate, Math, Map, Set, Promise, JSON, setTimeout, clearTimeout, setInterval, clearInterval };
  sandbox.globalThis = sandbox; sandbox.self = sandbox; sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(moreSource, sandbox, { filename: 'site/app-more.js' });
  const api = sandbox.module.exports;
  return api.views.player(api.model.resolve('#player/CFB/4870883'));
};

test('Under review shows no projection, chance or edge, and quotes only the saved recent volumes', async () => {
  const page = await playerPage(true);
  assert.match(page, /UNDER REVIEW/);
  assert.match(page, /No grade from me tonight\. My workload number for him is far below his last three full games \(50, 36 and 43 pass attempts\), so I&#39;m checking his role first\./);
  for (const banned of ['23.7', '167.1', '270.1', 'My average', 'I have', '57.0%', '53.3%', 'clears my price']) assert.ok(!page.includes(banned), banned);
  assert.match(page, /Both sides <b class="num">−114<\/b> at FanDuel\./);
  assert.match(page, /class="kt-hero kt-order"/);
  assert.match(page, /<table class="kt-log">/);
  assert.match(page, /<button type="button" data-set="pstat:passYds" aria-pressed="true">/);
});

test('a player line with no hold keeps its price check and the projection sentence', async () => {
  const page = await playerPage(false);
  assert.doesNotMatch(page, /UNDER REVIEW|No grade from me/);
  assert.match(page, /I have over at<b class="num">57\.0%<\/b>/);
  assert.match(page, /My average for this game: <b class="num">167\.1<\/b>/);
});

/* A soft pass defense for NMSU (rank 3 of 3), so an unheld over reads "supports the over". */
const softDefense = files => {
  files['data/app/teams/CFB.json'].teams['2'] = { abbr: 'XYZ', name: 'Other', fbs: true };
  files['data/app/teams/CFB.json'].defense = { rows: { 166: { g: 5, QB: { passYds: 300 } }, 2229: { g: 5, QB: { passYds: 200 } }, 2: { g: 5, QB: { passYds: 150 } } } };
};

test('Under review carries no directional verdict and never one side\'s price alone', async () => {
  const clean = await playerPage(false, softDefense);
  assert.match(clean, /NMSU allows 300 pass yds a game<\/b>[\s\S]*That supports the over\./, 'the fixture does produce a verdict when nothing is held');
  const held = await playerPage(true, files => {
    softDefense(files);
    files['data/app/lines-CFB.json'].lines[0].priceSuspect = true;      // the over's price failed: only the under is left
  });
  assert.match(held, /NMSU allows 300 pass yds a game/, 'the matchup fact stays');
  assert.doesNotMatch(held, /supports|works against/);
  assert.match(held, /Main line <b class="num">261\.5<\/b> at FanDuel\./);
  assert.doesNotMatch(held, /Under <b class="num">/, 'one side alone would read as a lean');
});

test('held words are shared by the Today ticket, the play page and the player page', () => {
  assert.equal(M.heldWords({ kind: 'qb' }), "His team's quarterback picture changed, so I'm checking his role first.");
  assert.equal(M.heldWords({ kind: 'workload', recentFull: [9, 7, 8], volume: 'targets' }),
    'My workload number for him is far below his last three full games (9, 7 and 8 targets), so I\'m checking his role first.');
  assert.equal(M.heldWords({ kind: 'price' }), "That price failed my sanity check, so I'm checking it first.");
  assert.match(M.heldWords({ kind: 'role' }), /doesn't match his recent full games/);
  assert.equal(M.heldShort({ kind: 'qb' }), 'Under review · checking his role first.');
  assert.deepEqual(M.holdOf([{ roleSuspect: true, priceSuspect: true, roleHold: 'qb' }]), { kind: 'qb' });
  assert.deepEqual(M.holdOf([{ priceSuspect: true }]), { kind: 'price' });
  assert.equal(M.holdOf([{ odds: -110 }]), null);
  assert.match(moreSource, /heldWords\(holdOf\(pricedRows\)/, 'the player page uses the same words');
});

test('the split panel never draws two teams of one hue as one slab', () => {
  const [a, b] = M.splitColours({ away: { color: '#00338d', alt: '#c60c30' }, home: { color: '#003594', alt: '#ffd100' } });
  const gap = (x, y) => Math.hypot(...[1, 3, 5].map(i => parseInt(x.slice(i, i + 2), 16) - parseInt(y.slice(i, i + 2), 16)));
  assert.ok(gap(a, b) >= 72, `${a} vs ${b}`);
  assert.deepEqual(M.splitColours({ away: { color: '#cc0033', alt: '#003366' }, home: { color: '#eaaa00', alt: '#002855' } }).map(c => c.toUpperCase()),
    ['#9F0028', '#002855'], 'distinct teams keep their own panels');
});

test("every chef's line with a photo ticket stays clear of the breakout head", () => {
  const css = fs.readFileSync('site/app.css', 'utf8');
  assert.match(css, /\.kt-lede\.with-photo h1 \{ max-width: 196px; \}/, 'the width cap wraps anything the estimate misses');
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'today', 'tonight'];
  for (const n of ['One', 'Two', 'Three', 'Four', 'Five', 'Six'])
    for (const day of days) {
      const title = `${n} for ${day}.`, size = M.ledeSize(title) || 32;
      /* Barlow Condensed 700 runs about 0.37 em a character (0.40 with wide letters such as W); measured at 32 px,
         "Three for Wednesday." is 256 px and "One for tonight." 182 px. */
      assert.ok(title.length * 0.40 * size <= 200 || (size === 32 && title.length * 0.37 * size <= 196), `${title} at ${size}px`);
    }
});

test('long two-line names stay at 24 px or less so they clear the matchup row', () => {
  assert.ok(M.nameSize('Marvin Harrison-Washington') <= 24);
  assert.ok(M.nameSize('Marcellous Hawkins Jr.') <= 24);
  assert.equal(M.nameSize('TK King'), 46);
});
