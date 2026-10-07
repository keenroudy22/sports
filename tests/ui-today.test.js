'use strict';
/* The Kitchen Ticket Today (OWNER-DECISIONS 2026-10-07 item 22; DIRECTION-RULES section 5 as updated by it): the chef's
   line with the last game day's W-L, the first best bet hanging on the rail, the Climb stub, then Leftovers, the
   Prep List and a closed "More for today" fold. today-hero.json paints the same top before today.json lands. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
globalThis.KRCore = C;
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const css = fs.readFileSync('site/app.css', 'utf8');
const html = fs.readFileSync('site/index.html', 'utf8');

/* Saturday Oct 10, 2026, 10:00 AM Eastern. */
const NOW = Date.parse('2026-10-10T14:00:00Z');
const chance = { chance: 0.56, breakEven: 0.524, edgePoints: 3.6, calibrated: true };
const prop = {
  id: 'NFL-2026-W5-fixture-rec-fd', kind: 'props', league: 'NFL', gameId: 'NFL-1', athleteId: '9', market: 'recYds', position: 'WR',
  displayTitle: 'Fixture Receiver OVER 49.5 receiving yards', line: 49.5, direction: 'over', odds: -110, book: 'FanDuel',
  kickoff: '2026-10-10T20:00:00Z', expiresAt: '2026-10-10T19:00:00Z', featured: true, posted: true, status: 'active', cutoffOdds: -124,
  publishedAt: '2026-10-10T13:00:00Z', probabilityAtPublication: chance, modelLean: true, side: 'away',
  ticketWhy: 'I project 7.3 targets, AWY\'s top WR.', ticketBut: 'HOM\'s WR defense points against the over.',
  hitStrip: { v: [78, 94, 67, 26, 21], season: [3, 5], last10: [5, 10] },
};
const total = { ...prop, id: 'CFB-2026-W6-fixture-total-dk', kind: 'gamePicks', league: 'CFB', gameId: 'CFB-2', athleteId: null, position: null,
  market: null, marketType: 'total', displayTitle: 'Fixture State at Example Tech over 51.5', line: 51.5, odds: -105, side: null, hitStrip: null,
  ticketWhy: null, ticketBut: null, book: 'DraftKings', kickoff: '2026-10-10T23:00:00Z', expiresAt: '2026-10-10T22:00:00Z', featured: false, posted: false };
const laterOpen = { ...total, id: 'CFB-2026-W7-later-open-dk', displayTitle: 'Later Open at Somewhere under 44.5',
  kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z' };
const laterOff = { ...total, id: 'CFB-2026-W7-later-off-fd', displayTitle: 'Moved Line at Elsewhere under 56.5',
  kickoff: '2026-10-13T00:15:00Z', status: 'expired', entryNote: 'Closed to new entries at 11:45 AM ET: total moved 3 against, from 56.5 to 53.5.' };
const yesterday = { ...total, id: 'NFL-2026-W5-yesterday-dk', displayTitle: 'Graded Yesterday over 40.5', line: 40.5, kickoff: '2026-10-09T23:00:00Z',
  result: 'win', units: 0.95, settledAt: '2026-10-10T03:00:00Z', actual: 'Visitors 24, Hosts 21' };
/* Three settled Climb rungs: climb 2, step 3, $94 riding, $42 banked. */
const rung = (id, step, run, result, ladder, kickoff) => ({ id, kind: 'parlays', parlayType: 'ladder', league: 'NFL', legs: ['Leg A over 40.5', 'Leg B over 3.5'],
  displayTitle: `Climb step ${step}`, odds: -150, book: 'FanDuel', kickoff, publishedAt: kickoff, result, status: 'active', ladder: { step, run, ...ladder } });
const rungs = [rung('NFL-ladder-r0', 1, 1, 'loss', { stake: 50 }, '2026-09-20T17:00:00Z'),
  rung('NFL-ladder-r1', 1, 2, 'win', { stake: 50, payout: 94 }, '2026-09-27T17:00:00Z'),
  rung('NFL-ladder-r2', 2, 2, 'win', { stake: 75, payout: 117, banked: 19, bankedAfter: 42, nextStake: 94 }, '2026-10-02T23:00:00Z')];
const GAMES = [{ id: 'NFL-1', league: 'NFL', kickoff: prop.kickoff, state: 'pre', season: 2026,
  away: { id: '1', abbr: 'AWY', name: 'Visitors', color: '#a71930', alt: '#000000' }, home: { id: '2', abbr: 'HOM', name: 'Hosts', color: '#003594', alt: '#ffd100' } },
{ id: 'CFB-2', league: 'CFB', kickoff: total.kickoff, state: 'pre', season: 2026,
  away: { id: '12', abbr: 'ARIZ', name: 'Arizona', color: '#cc0033', alt: '#003366' }, home: { id: '277', abbr: 'WVU', name: 'West Virginia', color: '#eaaa00', alt: '#002855' } }];
const SEASON = { ALL: { wins: 35, losses: 35, pushes: 0, playoffs: false }, NFL: { wins: 25, losses: 25, pushes: 0, playoffs: false }, CFB: { wins: 10, losses: 10, pushes: 0, playoffs: false } };
const LAST = { ALL: { day: '2026-10-09', kickoff: '2026-10-09T23:00:00Z', wins: 1, losses: 0, pushes: 0, units: 0.95 } };
const RUNS = [{ h: 6, m: 45 }, { h: 8, m: 30 }, { h: 11, m: 45 }, { h: 17, m: 30 }, { h: 21, m: 0 }, { h: 23, m: 30 }];
const PREP = { CFB: { day: '2026-10-10', rows: [
  { league: 'CFB', gameId: 'CFB-2', kickoff: total.kickoff, athleteId: '77', player: 'Prep Player', team: 'ARIZ', teamColor: '#cc0033', pos: 'WR',
    stat: 'recYds', direction: 'over', line: 54.5, odds: -114, book: 'FanDuel', hits: 6, games: 6, clears: true },
  { league: 'CFB', gameId: 'CFB-2', kickoff: total.kickoff, athleteId: '78', player: 'History Only', team: 'WVU', teamColor: '#002855', pos: 'RB',
    stat: 'rushYds', direction: 'over', line: 60.5, odds: -110, book: 'DraftKings', hits: 5, games: 6, clears: false }] } };
const TODAY = { generatedAt: '2026-10-10T13:50:00Z', games: GAMES, picks: [prop, total, laterOpen, laterOff, yesterday, ...rungs],
  season: SEASON, lastSlate: LAST, deskRuns: RUNS, prep: PREP };
const HERO = {
  generatedAt: '2026-10-10T13:50:00Z', day: '2026-10-10', more: 0, season: SEASON, last: LAST, deskRuns: RUNS,
  bets: [{ ...prop, teams: { away: GAMES[0].away, home: GAMES[0].home } }, { ...total, teams: { away: GAMES[1].away, home: GAMES[1].home } }],
  climb: { run: 2, step: 3, riding: 94, banked: 42, settled: 3, saved: 42, net: 36, last: { result: 'win', step: 2 } },
};

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW])); }
  static now() { return NOW; }
}
const element = () => ({ innerHTML: '', options: [], value: '', hidden: false, dataset: {}, classList: { toggle() {}, add() {}, remove() {} },
  querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, focus() {} });
/* The real app.js in a browser-shaped sandbox. Each JSON file can be held back to test the first paint; `stored`
   is the visitor's saved browser state (a saved league filter, for example). */
const loadApp = (hash, held = {}, { hero = HERO, today = TODAY, stored = {}, extra = {} } = {}) => {
  const view = element();
  view.querySelector = s => (s === '.hero-first' && view.innerHTML.includes('hero-first') ? element() : null);
  const files = { 'data/app/today.json': today, 'data/app/today-hero.json': hero, ...extra };
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: C, KRLive: L, KRPersonal: P,
    location: { hash, origin: 'http://localhost', pathname: '/' }, history: { state: null, replaceState() {} },
    document: { hidden: true, body: element(), activeElement: null, title: '', querySelector: s => s === '#view' ? view : element(),
      querySelectorAll: () => [], createElement: element, head: { appendChild() {} }, addEventListener() {} },
    localStorage: { getItem: key => (key in stored ? JSON.stringify(stored[key]) : null), setItem: () => {} },
    fetch: async url => {
      if (held[url]) await held[url];
      if (!files[url]) return { ok: false, status: 404, json: async () => ({}) };
      return { ok: true, json: async () => JSON.parse(JSON.stringify(files[url])) };
    },
    scrollTo() {}, console, URL, URLSearchParams, Intl, Date: FixedDate, Math, Map, Set, Promise, JSON,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox; sandbox.self = sandbox; sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  return { api: sandbox.module.exports, view, sandbox };
};
const settle = async () => { for (let i = 0; i < 20; i++) await new Promise(r => setTimeout(r, 0)); };
const wait = ms => new Promise(r => setTimeout(r, ms));
/* The top of Today: the chef's line, the first ticket and the Climb stub, up to the stub's aside. */
const top = page => page.slice(page.indexOf('<section class="kt-lede'), page.indexOf('<p class="kt-aside">'));
const mondayNfl = { ...prop, id: 'NFL-2026-W6-monday-total-dk', kind: 'gamePicks', athleteId: null, market: null, marketType: 'total',
  displayTitle: 'Monday Visitors at Hosts under 54.5', featured: false, kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z' };
const cfbOnly = { ...HERO, bets: [HERO.bets[1]] };

test('the Climb status words still come from one function', () => {
  assert.equal(M.climbWords({ open: { step: 3 }, step: 3, settled: 2 }), 'Step 3 is live');
  assert.equal(M.climbWords({ step: 3, settled: 2, last: { result: 'win', step: 2 } }), 'Step 2 cashed · Step 3 is being checked · not posted yet');
  assert.equal(M.climbWords({ step: 1, settled: 0 }), 'The first step waits for two clean games');
});

test('the first paint hangs today on the rail, else the next game day, never a moved or pulled play', () => {
  const today = M.heroBets(HERO, NOW);
  assert.equal(today.today, true);
  assert.deepEqual(today.rows.map(r => r.id), [prop.id, total.id]);
  assert.deepEqual(M.heroBets(HERO, NOW, 'CFB').rows.map(r => r.id), [total.id]);
  const moved = { ...prop, id: 'moved-today', entryNote: 'Closed to new entries at 11:45 AM ET: moved.' };
  const pulled = { ...prop, id: 'pulled-today', entryNote: 'Pulled over news before its post went out.' };
  assert.deepEqual(M.heroBets({ bets: [moved, pulled, total] }, NOW).rows.map(r => r.id), [total.id], 'off the card and pulled stay off the rail');
  const next = M.heroBets({ bets: [laterOff, laterOpen, { ...laterOpen, id: 'later-day', kickoff: '2026-10-14T00:15:00Z' }] }, NOW);
  assert.equal(next.today, false);
  assert.deepEqual(next.rows.map(r => r.id), [laterOpen.id]);
  assert.deepEqual(M.heroBets({ bets: [yesterday] }, NOW).rows, []);
  assert.deepEqual(M.heroBets(null, NOW).rows, []);
  const nfl = M.heroBets({ bets: [...cfbOnly.bets, mondayNfl] }, NOW, 'NFL');
  assert.deepEqual([nfl.today, nfl.rows.map(r => r.id)], [false, [mondayNfl.id]], 'a league filter gets its own next game day');
});

test('the first paint and the full card draw the same top, so nothing moves when today.json lands', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate });
  const pending = api.views.today({ view: 'today' });
  await settle();
  const first = view.innerHTML;
  assert.match(first, /class="hero-first kt-today"/);
  assert.match(first, /<p class="date">Saturday, Oct 10\. Friday went 1-0\.<\/p><h1>Two for today\.<\/h1>/);
  assert.match(first, /Hot Plate \(POTD\)/);
  assert.match(first, /−110<\/b><i><\/i><b class="kt-book">FanDuel/, 'price and book are on the first paint');
  assert.match(first, /Today 4:00 PM/, 'kickoff is on the first paint');
  assert.match(first, /80\/20 Climb #2[\s\S]*Step 3[\s\S]*Being checked · not posted yet/, 'the Climb stub is on the first paint');
  release();
  const full = await pending;
  assert.doesNotMatch(full, /hero-first/);
  assert.equal(top(full), top(first), 'the chef\'s line, the first ticket and the Climb stub are identical on both paints');
  await settle();
});

test('Today runs rail, Climb, Leftovers, Prep List, then a closed More fold; Off the card never hangs on the rail', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const at = text => { const i = page.indexOf(text); assert.ok(i >= 0, `missing ${text}`); return i; };
  const order = ['class="kt-lede', 'class="kt-pass"', 'class="kt-sec kt-climb"', 'class="kt-sec kt-left"', 'class="kt-sec kt-prep"', 'class="kt-sec kt-fold"'].map(at);
  assert.deepEqual(order, order.slice().sort((a, b) => a - b), 'rail -> Climb -> Leftovers -> Prep List -> fold');
  assert.match(page, /<details class="kt-sec kt-fold" data-box="today-more"><summary>/, 'the fold starts closed');
  const rails = page.slice(0, at('class="kt-sec kt-left"'));
  assert.doesNotMatch(rails, /Moved Line at Elsewhere/, 'Off the card stays outside the rail');
  const off = page.slice(at('data-box="off-card"'));
  assert.match(off, /Off the card · 1[\s\S]*Moved Line at Elsewhere/);
  assert.match(page.slice(at('data-box="later"')), /Later Open at Somewhere/);
  assert.match(page, /<h2 class="kt-head" id="left-h">Friday went 1-0\.<\/h2>/);
  assert.match(page, /<span class="kt-stamp hit" aria-hidden="true">[\s\S]*?HIT<\/span>/);
  assert.match(page, /Final 24-21, cleared by 4\.5\./);
  assert.match(page, /Past steps · 3/, 'every completed rung stays one tap away');
  assert.match(page, /Step 2 cashed\./);
  for (const gone of ['class="onboard"', 'class="proof"', 'today-status', 'Research worth a look']) assert.ok(!page.includes(gone), gone);
  assert.match(page, /about 10–15 minutes before X/);
});

test('the Prep List shows only the rows the build chose, with the price check only where it clears', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const prep = page.slice(page.indexOf('class="kt-sec kt-prep"'), page.indexOf('class="kt-sec kt-fold"'));
  assert.match(prep, /<h2 class="kt-tape" id="prep-h">Prep List<\/h2><span class="kt-kind">Research for tonight<\/span>/);
  assert.match(prep, /Prep Player[\s\S]*Over 54\.5 rec yds[\s\S]*−114 FanDuel<span class="ok">✓ clears my price<\/span>/);
  assert.match(prep, /History Only[\s\S]*−110 DraftKings<span class="no">History only · no edge at this price<\/span><\/p>/, 'the playbook label on a row that does not clear');
  assert.match(prep, /<p class="kt-note">College injury news is thin\.<\/p>/, 'college rows carry the playbook note');
  assert.equal((prep.match(/✓ clears my price/g) || []).length, 1);
  const none = loadApp('#record', {}, { today: { ...TODAY, prep: {} } });
  assert.doesNotMatch(await none.api.views.today({ view: 'today' }), /kt-prep/, 'no rows from the build, no Prep List');
});

test('the first ticket carries no fair price or edge, and its numbers are the pick\'s own', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const first = page.slice(page.indexOf('<article class="kt-order'), page.indexOf('</article>') + 10);
  assert.match(first, /<p class="kt-chip"><svg[^>]*>.*?<\/svg>Hot Plate \(POTD\)<\/p>/, 'the exact Hot Plate (POTD) phrase');
  assert.match(first, /I have it at<b class="num">56\.0%<\/b><\/span><i><\/i><span>the price needs<b class="num">52\.4%<\/b>/);
  assert.match(first, /<span class="kt-tag">WHY<\/span><span>I project 7\.3 targets, AWY&#39;s top WR\.<\/span>/);
  assert.match(first, /<span class="kt-tag">BUT<\/span><span>HOM&#39;s WR defense points against the over\.<\/span>/);
  assert.match(first, /Still good to −124\./);
  assert.match(first, /Best bets this season<b class="num">35-35<\/b>/);
  assert.match(first, /3 of 5 this season<\/b>5 of his last 10/);
  for (const banned of ['Price matching our chance', 'Chance vs price', ' pts', 'fair', 'edge']) assert.ok(!first.includes(banned), banned);
  const text = first.replace(/<[^>]+>/g, ' ').replace(/&#\d+;/g, "'");
  const allowed = new Set(['49.5', '110', '56.0', '52.4', '7.3', '124', '35', '35', '78', '94', '67', '26', '21', '3', '5', '5', '10', '4', '00', '1', '2']);
  for (const n of text.match(/\d+(?:\.\d+)?/g) || []) assert.ok(allowed.has(n), `unexpected number ${n} on the ticket`);
});

test('an uncalibrated chance, an expired quote and a moved line never read as an open, good play', async () => {
  const { api } = loadApp('#record');
  await api.views.today({ view: 'today' });
  const ticketOf = (pick, opts) => {
    const { api: a } = loadApp('#record', {}, { today: { ...TODAY, picks: [pick] } });
    return a.views.today({ view: 'today' }).then(page => page.slice(page.indexOf('<article class="kt-order'), page.indexOf('</article>')));
  };
  const raw = await ticketOf({ ...prop, probabilityAtPublication: { chance: 0.6, breakEven: 0.524, calibrated: false } });
  assert.doesNotMatch(raw, /kt-chance|I have it at/, 'no chance row when the chance is uncalibrated');
  const aged = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z' });
  assert.match(aged, /Posted price may be gone\. Check your book\./);
  assert.match(aged, /I had it at/);
  assert.doesNotMatch(aged, /Still good to|I have it at/);
});

test('a hero that lands after today.json never paints over the full card', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view } = loadApp('#today', { 'data/app/today-hero.json': gate });
  const pending = api.views.today({ view: 'today' });
  await settle();
  assert.doesNotMatch(view.innerHTML, /hero-first/);
  release();
  await pending;
  await settle();
  assert.doesNotMatch(view.innerHTML, /hero-first/);
});

test("index.html's early hero request is reused, not repeated, by later Today renders", async () => {
  const { api, sandbox } = loadApp('#record');
  const asked = [];
  const fetchFile = sandbox.fetch;
  sandbox.fetch = (url, options) => { asked.push(url); return fetchFile(url, options); };
  sandbox.krHero = Promise.resolve(JSON.parse(JSON.stringify(HERO)));
  await api.views.today({ view: 'today' });
  await api.views.today({ view: 'today' });
  assert.equal(asked.filter(url => url.includes('today-hero')).length, 0);
  assert.equal(sandbox.krHero, null);
  await settle();
});

test('the shell requests the hero before render-blocking CSS and keeps the footer from jumping', () => {
  const early = html.indexOf("fetch('data/app/today-hero.json'");
  assert.ok(early > 0 && early < html.indexOf('rel="stylesheet"'));
  assert.match(source, /const early = window\.krHero;/);
  assert.match(source, /maybe\('app\/today-hero\.json'\)/);
  assert.match(css, /#view \{ min-height: 100vh; \}/);
  assert.match(source, /token === renderToken && !\(route\.view === 'today' && view\.querySelector\('\.hero-first'\)\)/);
  assert.doesNotMatch(html, /fast-hero/, 'the dead single-pick hint is gone; app.js paints the ticket silhouette');
});

test('tapping another tab before today.json lands replaces the hero with the loading line', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view, sandbox } = loadApp('#today', { 'data/app/today.json': gate });
  api.render();
  await settle();
  assert.match(view.innerHTML, /hero-first/);
  await wait(200);
  assert.match(view.innerHTML, /hero-first/, 'on Today the 150 ms placeholder leaves the painted hero alone');
  sandbox.location.hash = '#record';
  api.render();
  await wait(200);
  assert.doesNotMatch(view.innerHTML, /hero-first|Fixture Receiver/);
  assert.match(view.innerHTML, /Loading…/);
  release();
  await settle();
});

test('a league change repaints the hero for that league, and other sports clear it and never show football', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view, sandbox } = loadApp('#today', { 'data/app/today.json': gate });
  api.render();
  await settle();
  assert.match(view.innerHTML, /Fixture Receiver/);
  sandbox.location.hash = '#today?sport=CFB';
  api.render();
  await settle();
  assert.match(view.innerHTML, /hero-first/);
  assert.match(view.innerHTML, /Arizona/);
  assert.doesNotMatch(view.innerHTML, /Fixture Receiver/);
  sandbox.location.hash = '#today?sport=NBA';
  api.render();
  await settle();
  assert.doesNotMatch(view.innerHTML, /hero-first|Fixture/);
  release();
  await settle();
});

test('a saved league filter paints its own next game day, and never an empty hero', async () => {
  const { api: empty } = loadApp('#today', {}, { hero: cfbOnly, stored: { 'kr:league': 'NFL' } });
  assert.equal(empty.firstPaint(cfbOnly), '');
  const withNfl = { ...cfbOnly, bets: [...cfbOnly.bets, mondayNfl] };
  let release;
  const gate = new Promise(r => { release = r; });
  const next = loadApp('#today', { 'data/app/today.json': gate }, { hero: withNfl, stored: { 'kr:league': 'NFL' } });
  const pending = next.api.views.today({ view: 'today' });
  await settle();
  assert.match(next.view.innerHTML, /<h1>One for Monday\.<\/h1>/);
  assert.match(next.view.innerHTML, /Monday Visitors at Hosts under 54\.5/);
  assert.doesNotMatch(next.view.innerHTML, /Fixture State/);
  release();
  await pending;
  await settle();
});

test('with nothing on the card the rail hangs empty clips and names the next desk run', async () => {
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [yesterday, ...rungs] } });
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /<h1>Nothing on the rail yet\.<\/h1>/);
  assert.match(page, /class="kt-hook h1"[\s\S]*class="kt-hook h2"/);
  assert.match(page, /I look again at 11:45 AM\. <a href="#research\/trends">Tonight&#39;s research ›<\/a>|I look again at 11:45 AM\. <a href="#research\/trends">Tonight's research ›<\/a>/);
  assert.doesNotMatch(page, /<article class="kt-order/, 'no blank ticket and no forced pick');
});

test('Leftovers never drop a miss while a hit stays, and count the rest', async () => {
  const day = (i, result) => ({ ...yesterday, id: `NFL-2026-W5-day-${i}`, result, kickoff: `2026-10-09T${10 + i}:00:00Z` });
  const settled = [day(1, 'loss'), day(2, 'win'), day(3, 'win'), day(4, 'win'), day(5, 'win'), day(6, 'win'), day(7, 'loss')];
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [prop, ...settled, ...rungs], lastSlate: { ALL: { day: '2026-10-09', wins: 5, losses: 2, pushes: 0 } } } });
  const page = await api.views.today({ view: 'today' });
  const left = page.slice(page.indexOf('class="kt-sec kt-left"'), page.indexOf('class="kt-sec kt-prep"'));
  assert.equal((left.match(/kt-stamp miss/g) || []).length, 2, 'both misses stay');
  assert.equal((left.match(/class="kt-spiked"/g) || []).length, 3, 'three slips, so the Prep List stays one short scroll away');
  assert.match(left, /\+4 more on the record ›/);
  assert.match(left, /Friday went 5-2\./);
});

test('HIT, MISS and push stamps share one size; results never rely on colour alone', () => {
  const rule = name => (css.match(new RegExp(`\\.kt-stamp\\.${name} \\{([^}]*)\\}`)) || [])[1] || '';
  for (const name of ['hit', 'miss', 'hold']) assert.doesNotMatch(rule(name), /font|padding|width|height/, name);
  assert.match(source, /HIT<\/span>/);
  assert.match(source, /MISS<\/span>/);
  assert.match(source, /'VOID' : 'PUSH'/);
});

/* TK King, Oct 7: the Hot Plate's market was on a QB-change hold with a failed price check, while a fresh same-book
   row said −104. Nothing may call that play still good, give its chance, or show its fair price and edge. */
const KING_HOLD = { kind: 'qb' };
const heldProp = { ...prop, expiresAt: '2026-10-09T21:30:00Z', held: KING_HOLD };
const kingRow = { id: 'prop-NFL-1-9-recYds', gameId: 'NFL-1', athleteId: '9', stat: 'recYds', market: 'receiving yards', direction: 'over', line: 49.5,
  odds: -104, book: 'FanDuel', state: 'open', observedAt: '2026-10-10T13:37:35Z', kickoff: prop.kickoff, roleSuspect: true, priceSuspect: true, roleHold: 'qb', grade: null };
const linesFor = rows => ({ 'data/app/lines.json': { files: { NFL: 'lines-NFL.json', CFB: 'lines-CFB.json' } },
  'data/app/lines-NFL.json': { league: 'NFL', lines: rows }, 'data/app/lines-CFB.json': { league: 'CFB', lines: [] } });
const firstTicket = page => page.slice(page.indexOf('<article class="kt-order'), page.indexOf('</article>'));

test('a held market never yields a quote, and its hold comes from the build or from any of its rows', () => {
  assert.equal(M.latestPickQuote({ ...prop, held: KING_HOLD }, [{ ...kingRow, roleSuspect: false, priceSuspect: false, roleHold: null }], NOW), null);
  assert.equal(M.latestPickQuote(prop, [kingRow], NOW), null, 'a held same-book row is never a live quote');
  assert.deepEqual(M.pickHold(prop, [kingRow]), { kind: 'qb' }, 'no build field: the board rows hold it');
  assert.deepEqual(M.pickHold(prop, [{ ...kingRow, book: 'DraftKings', direction: 'under' }]), { kind: 'qb' }, 'any book, either side');
  assert.equal(M.pickHold({ ...prop, result: 'win' }, [kingRow]), null, 'a settled play is graded, not held');
});

test('the held Hot Plate reads Under review on the first paint and the full card, with no chance and no ORDER UP', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const hero = { ...HERO, bets: [{ ...heldProp, teams: HERO.bets[0].teams }, HERO.bets[1]] };
  const today = { ...TODAY, picks: [heldProp, total, laterOpen, laterOff, yesterday, ...rungs] };
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate }, { hero, today, extra: linesFor([{ ...kingRow, roleSuspect: false, priceSuspect: false, roleHold: null }]) });
  const pending = api.views.today({ view: 'today' });
  await settle();
  const first = firstTicket(view.innerHTML);
  release();
  const full = await pending;
  await settle();
  const again = firstTicket(await api.views.today({ view: 'today' }));     // after the board rows land
  for (const t of [first, firstTicket(full), again]) {
    assert.match(t, /<p class="kt-now">Under review · checking his role first\.<\/p>/);
    assert.match(t, /class="kt-order[^"]*is-held/);
    for (const banned of ['Still good', 'I have it', 'I had it', 'kt-chance', 'kt-orderup', 'Now −', '56.0%']) assert.ok(!t.includes(banned), banned);
    assert.match(t, /−110<\/b><i><\/i><b class="kt-book">FanDuel/, 'the posted price and book stay');
  }
  assert.equal(first, firstTicket(full), 'both paints say the same thing');
});

test('an expired saved quote with a fresh same-book price reads the same on both paints', async () => {
  const aged = { ...prop, expiresAt: '2026-10-10T12:00:00Z', quote: { odds: -115, line: 49.5, observedAt: '2026-10-10T13:20:00Z' } };
  let release;
  const gate = new Promise(r => { release = r; });
  const hero = { ...HERO, bets: [{ ...aged, teams: HERO.bets[0].teams }, HERO.bets[1]] };
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate }, { hero, today: { ...TODAY, picks: [aged, total, ...rungs] } });
  const pending = api.views.today({ view: 'today' });
  await settle();
  const first = firstTicket(view.innerHTML);
  release();
  const full = firstTicket(await pending);
  await settle();
  assert.match(first, /Now −115 at 9:20 AM\. Still good to −124\./);
  assert.match(first, /I have it at/);
  assert.equal(first, full);
  const stale = { ...aged, quote: { ...aged.quote, observedAt: '2026-10-10T09:00:00Z' } };
  const { api: a2 } = loadApp('#record', {}, { today: { ...TODAY, picks: [stale, ...rungs] } });
  const t = firstTicket(await a2.views.today({ view: 'today' }));
  assert.match(t, /Posted price may be gone\. Check your book\./, 'older than four hours at view time: the browser drops it');
  assert.match(t, /I had it at/);
});

test('a settled ticket never wears ORDER UP', async () => {
  const { api } = loadApp('#record', {}, { today: TODAY, extra: {} });
  const page = await api.views.pick({ id: yesterday.id });
  assert.match(page, /kt-stamp hit/);
  assert.doesNotMatch(page, /kt-orderup|ORDER UP/);
  const open = await loadApp('#record').api.views.pick({ id: prop.id });
  assert.match(open, /ORDER UP/, 'an open best bet does');
});

test('the play page under review shows no fair price, edge, chance or projection, and keeps the posted price', async () => {
  const king = { ...prop, held: KING_HOLD, projection: 68.2, cutoff: 'Good to −124 at 49.5.', why: 'Our model projects 68.2.',
    probabilityAtPublication: { chance: 0.537, rawChance: 0.659, calibration: 0.23, calibrationN: 398, breakEven: 0.505, edgePoints: 3.2, calibrated: true } };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [king, ...rungs] }, extra: linesFor([kingRow]) });
  const page = await api.views.pick({ id: king.id });
  assert.match(page, /<h2 class="kt-tape">The hold<\/h2>/);
  assert.match(page, /UNDER REVIEW/);
  assert.match(page, /His team&#39;s quarterback picture changed, so I&#39;m checking his role first\./);
  assert.match(page, /graded at −110 at FanDuel, the price we posted/);
  for (const banned of ['My price', 'How we got', 'projects', '68.2', '53.7%', '65.9%', '+3.2', '−116', 'Still good', 'Still a bet down to', 'I have it', 'Price we would still play', 'Our notes when we posted'])
    assert.ok(!page.includes(banned), banned);
  assert.match(page, /data-held="1"/, 'the history box drops its defense verdict too');
  const clean = await loadApp('#record', {}, { today: { ...TODAY, picks: [{ ...king, held: undefined }, ...rungs] } }).api.views.pick({ id: king.id });
  assert.match(clean, /How we got 53\.7%/, 'one decimal, matching the ticket');
  assert.match(clean, /My price/);
});

test('a Climb step page keeps its saved stake and return, and every play page links the Discord and X', async () => {
  const step = { ...rungs[1], reason: 'Ladder step 1 of the climb. $50 rides with $0 banked. A win returns $94: bank $19 and ride $75 on the next step.' };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [prop, step, rungs[0], rungs[2]] } });
  const page = await api.views.pick({ id: step.id });
  assert.match(page, /<h2 class="kt-tape">The stake<\/h2><p>Ladder step 1 of the climb\. \$50 rides with \$0 banked\. A win returns \$94/);
  assert.match(page, /discord\.gg\/ZnjubjsBPM/);
  assert.match(page, /x\.com\/keenkooks/);
  assert.match(page, /<section class="kt-pass on-page" aria-label="Best bet">/, 'a play page for another day is not labelled today\'s');
});

test('Today headings run h1, then h2 for each ticket and section', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const levels = [...page.matchAll(/<h([1-6])[ >]/g)].map(m => Number(m[1]));
  assert.equal(levels[0], 1);
  for (let i = 1; i < levels.length; i++) assert.ok(levels[i] <= levels[i - 1] + 1, `h${levels[i - 1]} then h${levels[i]}`);
  assert.match(page, /<h2 class="kt-name"/);
});

test('WHY and BUT print the saved words whole: clamped on the Today rail only, never cut in the markup', async () => {
  const long = 'Bowling Green cornerback JoJo Johnson, who had 13 pass breakups last season, missed the Iowa State game due to injury.';
  const pick = { ...prop, ticketWhy: long };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [pick, ...rungs] } });
  const today = await api.views.today({ view: 'today' });
  assert.ok(today.includes(long.replace("'", '&#39;')), 'the full sentence is in the Today ticket');
  assert.match(css, /\.kt-pass:not\(\.on-page\) \.kt-say > span:last-child \{[^}]*-webkit-line-clamp: 2/);
  const page = await api.views.pick({ id: pick.id });
  assert.match(page, /<section class="kt-pass on-page"/, 'the play page is exempt from the clamp');
  assert.ok(page.includes(long));
});
