'use strict';
/* The owner's 10-second Today (DIRECTION-RULES section 5): the Climb and last game day as compact rows with the
   first best bet above the fold, today-hero.json painted before the full today.json, off-the-card plays out of
   "More best bets", and the extras folded under "More for today". */
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
  id: 'NFL-2026-W5-fixture-rec-fd', kind: 'props', league: 'NFL', gameId: 'NFL-1', athleteId: '9', market: 'recYds',
  displayTitle: 'Fixture Receiver over 49.5 receiving yards', line: 49.5, direction: 'over', odds: -110, book: 'FanDuel',
  kickoff: '2026-10-10T20:00:00Z', expiresAt: '2026-10-10T19:00:00Z', featured: true, posted: true, status: 'active',
  publishedAt: '2026-10-10T13:00:00Z', probabilityAtPublication: chance, modelLean: true,
};
const total = { ...prop, id: 'CFB-2026-W6-fixture-total-dk', kind: 'gamePicks', league: 'CFB', gameId: 'CFB-2', athleteId: null,
  market: null, marketType: 'total', displayTitle: 'Fixture State at Example Tech over 51.5', line: 51.5, odds: -105,
  book: 'DraftKings', kickoff: '2026-10-10T23:00:00Z', expiresAt: '2026-10-10T22:00:00Z', featured: false, posted: false };
const laterOpen = { ...total, id: 'CFB-2026-W7-later-open-dk', displayTitle: 'Later Open at Somewhere under 44.5',
  kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z' };
const laterOff = { ...total, id: 'CFB-2026-W7-later-off-fd', displayTitle: 'Moved Line at Elsewhere under 56.5',
  kickoff: '2026-10-13T00:15:00Z', status: 'expired', entryNote: 'Closed to new entries at 11:45 AM ET: total moved 3 against, from 56.5 to 53.5.' };
const yesterday = { ...total, id: 'NFL-2026-W5-yesterday-dk', displayTitle: 'Graded Yesterday over 40.5', kickoff: '2026-10-09T23:00:00Z',
  result: 'win', units: 0.95, settledAt: '2026-10-10T03:00:00Z' };
/* Three settled Climb rungs that leave the ledger where HERO.climb says it is: climb 2, step 3, $94 riding, $42 banked. */
const rung = (id, step, run, result, ladder, kickoff) => ({ id, kind: 'parlays', parlayType: 'ladder', league: 'NFL', legs: ['Leg A', 'Leg B'],
  displayTitle: `Climb step ${step}`, odds: -150, book: 'FanDuel', kickoff, publishedAt: kickoff, result, status: 'active', ladder: { step, run, ...ladder } });
const rungs = [rung('NFL-ladder-r0', 1, 1, 'loss', { stake: 50 }, '2026-09-20T17:00:00Z'),
  rung('NFL-ladder-r1', 1, 2, 'win', { stake: 50, payout: 94 }, '2026-09-27T17:00:00Z'),
  rung('NFL-ladder-r2', 2, 2, 'win', { stake: 75, payout: 117, banked: 19, bankedAfter: 42, nextStake: 94 }, '2026-10-02T23:00:00Z')];
const TODAY = { generatedAt: '2026-10-10T13:50:00Z', games: [], picks: [prop, total, laterOpen, laterOff, yesterday, ...rungs] };
const HERO = {
  generatedAt: '2026-10-10T13:50:00Z', day: '2026-10-10', more: 0,
  bets: [{ ...prop, card: 'data/cards/NFL-2026-W5-fixture-rec-fd-potd.png' }, { ...total, card: 'data/cards/CFB-2026-W6-fixture-total-dk.png' }],
  climb: { run: 2, step: 3, riding: 94, banked: 42, settled: 3, last: { result: 'win', step: 2 } },
  last: { ALL: { day: '2026-10-09', kickoff: '2026-10-09T23:00:00Z', wins: 1, losses: 0, pushes: 0, units: 0.95 } },
};

class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW])); }
  static now() { return NOW; }
}
const element = () => ({ innerHTML: '', options: [], value: '', hidden: false, dataset: {}, classList: { toggle() {}, add() {}, remove() {} },
  querySelector: () => null, querySelectorAll: () => [], setAttribute() {}, focus() {} });
/* The real app.js in a browser-shaped sandbox. Each JSON file can be held back to test the first paint; `stored`
   is the visitor's saved browser state (a saved league filter, for example). */
const loadApp = (hash, held = {}, { hero = HERO, stored = {} } = {}) => {
  const view = element();
  /* The page view answers the one selector the renderer asks of it: is a first-paint hero on screen? */
  view.querySelector = s => (s === '.hero-first' && view.innerHTML.includes('hero-first') ? element() : null);
  const files = { 'data/app/today.json': TODAY, 'data/app/today-hero.json': hero };
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
/* Monday night's NFL play: the only NFL best bet in the hero when today's card is all college. */
const mondayNfl = { ...prop, id: 'NFL-2026-W6-monday-total-dk', kind: 'gamePicks', athleteId: null, market: null, marketType: 'total',
  displayTitle: 'Monday Visitors at Hosts under 54.5', featured: false, kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z',
  card: 'data/cards/NFL-2026-W6-monday-total-dk.png' };
const cfbOnly = { ...HERO, bets: [{ ...total, card: 'data/cards/CFB-2026-W6-fixture-total-dk.png' }] };

test('the Climb status words are shared by the first paint and the full ledger', () => {
  assert.equal(M.climbWords({ open: { step: 3 }, step: 3, settled: 2 }), 'Step 3 is live');
  assert.equal(M.climbWords({ step: 3, settled: 2, last: { result: 'win', step: 2 } }), 'Step 2 cashed · Step 3 is being checked · not posted yet');
  assert.equal(M.climbWords({ step: 1, settled: 4, last: { result: 'loss', step: 1 } }), 'New $50 climb · Step 1 is being checked · not posted yet');
  assert.equal(M.climbWords({ step: 2, settled: 2, last: { result: 'push', step: 2 } }), 'Step 2 is being checked · not posted yet');
  assert.equal(M.climbWords({ step: 1, settled: 0 }), 'The first step waits for two clean games');
  assert.match(source, /const climbStatus = lad => climbWords\(climbSummary\(lad\)\)/, 'the full ledger uses the same words');
  assert.match(source, /const statusRows = [\s\S]*?esc\(climbWords\(c\)\)/, 'so do the status rows on both Today paints');
});

test('the first paint shows today, else the next game day still on the card, never a stale or moved play', () => {
  const today = M.heroBets(HERO, NOW);
  assert.equal(today.today, true);
  assert.deepEqual(today.rows.map(r => r.id), [prop.id, total.id]);
  assert.deepEqual(M.heroBets(HERO, NOW, 'CFB').rows.map(r => r.id), [total.id]);
  assert.deepEqual(M.heroBets({ bets: [laterOff, total] }, NOW).rows.map(r => r.id), [total.id],
    'an off-the-card play never appears as a best bet on the first paint');
  const nextOnly = { bets: [laterOff, laterOpen, { ...laterOpen, id: 'later-day', kickoff: '2026-10-14T00:15:00Z' }] };
  const next = M.heroBets(nextOnly, NOW);
  assert.equal(next.today, false);
  assert.deepEqual(next.rows.map(r => r.id), [laterOpen.id], 'off-the-card plays and later days stay out');
  assert.deepEqual(M.heroBets({ bets: [yesterday] }, NOW).rows, [], 'a hero built before midnight never shows yesterday as today');
  assert.deepEqual(M.heroBets(null, NOW).rows, []);
  const perLeague = { bets: [...cfbOnly.bets, mondayNfl] };
  assert.deepEqual(M.heroBets(perLeague, NOW).rows.map(r => r.id), [total.id], 'all sports: today first, another league\'s later day waits');
  const nfl = M.heroBets(perLeague, NOW, 'NFL');
  assert.equal(nfl.today, false);
  assert.deepEqual(nfl.rows.map(r => r.id), [mondayNfl.id], 'an NFL filter gets the next NFL game day, as the full card does');
});

test('Today paints today-hero.json while today.json is still loading, then the full card replaces it', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate });
  const pending = api.views.today({ view: 'today' });
  await settle();
  assert.match(view.innerHTML, /class="section today-bets hero-first"/, 'the hero is painted before today.json arrives');
  assert.match(view.innerHTML, /Pick of the Day/);
  assert.match(view.innerHTML, /Fixture Receiver over 49\.5 receiving yards/);
  assert.match(view.innerHTML, /-110<\/b><span>FanDuel/, 'price and book are on the first paint');
  assert.match(view.innerHTML, /kicks off in 6h 0m/, 'kickoff is on the first paint');
  assert.match(view.innerHTML, /href="data\/cards\/NFL-2026-W5-fixture-rec-fd-potd\.png"[^>]*>See the card/);
  assert.match(view.innerHTML, /<b>80\/20 Climb<\/b> · Step 2 cashed · Step 3 is being checked · not posted yet · \$94 riding · \$42 banked/);
  assert.match(view.innerHTML, /<b>Last game day<\/b> · Friday, Oct 9 · 1–0 · \+0\.95u/);
  const firstTicket = view.innerHTML.indexOf('<article class="ticket');
  assert.ok(view.innerHTML.indexOf('class="today-status"') < firstTicket, 'the Climb and last game day rows sit above the first ticket');
  assert.ok(view.innerHTML.indexOf('Last game day') < firstTicket);
  assert.ok(view.innerHTML.indexOf('Fixture Receiver') < view.innerHTML.indexOf('Fixture State'), 'Pick of the Day leads');
  const firstPaint = view.innerHTML;
  release();
  const full = await pending;
  assert.match(full, /class="today-more"/);
  assert.doesNotMatch(full, /hero-first/);
  /* The same two rows, in the same words and order, sit above the first ticket on both paints. */
  const rows = html => (html.slice(0, html.indexOf('<article class="ticket')).match(/<span><b>[^<]+<\/b> · [^<]*<\/span>/g) || []);
  assert.equal(rows(full).length, 2);
  assert.deepEqual(rows(full), rows(firstPaint), 'the full card keeps the first paint\'s status words in the same place');
  await settle();
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
  assert.doesNotMatch(view.innerHTML, /hero-first/, 'today.json landed first, so the hero stays unpainted');
});

test("index.html's early hero request is reused, not repeated, by later Today renders", async () => {
  const { api, sandbox } = loadApp('#record');
  const asked = [];
  const fetchFile = sandbox.fetch;
  sandbox.fetch = (url, options) => { asked.push(url); return fetchFile(url, options); };
  sandbox.krHero = Promise.resolve(JSON.parse(JSON.stringify(HERO)));
  const first = await api.views.today({ view: 'today' });
  const second = await api.views.today({ view: 'today' });
  for (const page of [first, second]) assert.match(page, /href="data\/cards\/NFL-2026-W5-fixture-rec-fd-potd\.png"/);
  assert.equal(asked.filter(url => url.includes('today-hero')).length, 0);
  assert.equal(sandbox.krHero, null);
  await settle();
});

test('Today shows the Climb, the last game day and the first best bet together, then folds the extras', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const at = text => { const i = page.indexOf(text); assert.ok(i >= 0, `missing ${text}`); return i; };
  const bet = at('Fixture Receiver over 49.5 receiving yards');
  assert.ok(at('<h1>') < at('class="today-status"') && at('class="today-status"') < bet, 'two compact status rows sit between the heading and the first ticket');
  const climb = page.slice(at('data-box="climb-status"'), at('data-box="last-day"'));
  assert.match(climb, /^data-box="climb-status"><summary><span><b>80\/20 Climb<\/b> · Step 2 cashed · Step 3 is being checked · not posted yet · \$94 riding · \$42 banked<\/span><\/summary>/,
    'the Climb row uses the shared words, the stake and the bank');
  assert.match(climb, /Past steps · 3/, 'it opens to the full ledger in one tap');
  const last = page.slice(at('data-box="last-day"'), bet);
  assert.match(last, /<b>Last game day<\/b> · Friday, Oct 9 · 1–0 · \+0\.95u/);
  assert.match(last, /Graded Yesterday over 40\.5/, 'it opens to the receipts in one tap');
  assert.equal(page.split('data-box="climb-status"').length, 2, 'the Climb status appears once, not again under the tickets');
  assert.ok(bet < at('class="proof"'), 'the season line sits below the first best bet');
  assert.ok(bet < at('New here?'), 'the welcome note sits below the first best bet');
  assert.match(page, /href="data\/cards\/NFL-2026-W5-fixture-rec-fd-potd\.png"/, 'the full card keeps the share-card link');
  const more = page.slice(at('More best bets'), at('data-box="off-card"'));
  assert.match(more, /Later Open at Somewhere/);
  assert.doesNotMatch(more, /Moved Line at Elsewhere/, 'an off-the-card play is out of More best bets');
  const off = page.slice(at('data-box="off-card"'), page.indexOf('</details>', at('data-box="off-card"')));
  assert.match(off, /Off the card · 1/);
  assert.match(off, /Moved Line at Elsewhere/);
  assert.match(off, /graded at its posted price/);
  const foldAt = at('<details class="today-more"');
  const fold = page.slice(foldAt);
  assert.match(fold, /^<details class="today-more" data-box="today-more"><summary>More for today/, 'the fold starts collapsed');
  for (const heading of ['<h2>Underdog watch</h2>', '<h2>Today&#39;s games</h2>']) {
    assert.ok(page.indexOf(heading) > foldAt, `${heading} sits inside More for today`);
  }
  assert.ok(at('Research worth a look') < foldAt);
});

test('the shell requests the hero before render-blocking CSS and keeps the footer from jumping', () => {
  const early = html.indexOf("fetch('data/app/today-hero.json'");
  assert.ok(early > 0, 'index.html starts the hero request');
  assert.ok(early < html.indexOf('rel="stylesheet"'), 'the inline request runs before any stylesheet can block it');
  assert.match(html, /window\.krHero=/);
  assert.match(source, /const early = window\.krHero;/);
  assert.match(source, /maybe\('app\/today-hero\.json'\)/, 'other entry routes still fetch the hero');
  assert.match(css, /#view \{ min-height: 100vh; \}/);
  assert.match(source, /token === renderToken && !\(route\.view === 'today' && view\.querySelector\('\.hero-first'\)\)/,
    'the loading placeholder never wipes a painted hero on Today, and always replaces it on another page');
});

test('tapping another tab before today.json lands replaces the hero with the loading line', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view, sandbox } = loadApp('#today', { 'data/app/today.json': gate });
  api.render();
  await settle();
  assert.match(view.innerHTML, /hero-first/, 'the hero is up while today.json is on its way');
  await wait(200);
  assert.match(view.innerHTML, /hero-first/, 'on Today the 150 ms placeholder leaves the painted hero alone');
  sandbox.location.hash = '#record';
  api.render();
  await wait(200);
  assert.doesNotMatch(view.innerHTML, /hero-first|Fixture Receiver/, "Record never shows Today's hero");
  assert.match(view.innerHTML, /Loading…/);
  release();
  await settle();
});

test('a league change before today.json lands repaints the hero for that league, and other sports clear it', async () => {
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
  assert.match(view.innerHTML, /Fixture State at Example Tech/);
  assert.doesNotMatch(view.innerHTML, /Fixture Receiver/, 'the NFL play leaves a college-only first paint');
  sandbox.location.hash = '#today?sport=NBA';
  api.render();
  await settle();
  assert.doesNotMatch(view.innerHTML, /hero-first|Fixture/, 'NBA never shows the football hero');
  release();
  await settle();
});

test('a saved league filter paints its own next best bet, and never an empty hero', async () => {
  const { api: empty } = loadApp('#today', {}, { hero: cfbOnly, stored: { 'kr:league': 'NFL' } });
  assert.equal(empty.firstPaint(cfbOnly), '', 'no NFL play in the hero: wait for the full card');
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate }, { hero: cfbOnly, stored: { 'kr:league': 'NFL' } });
  const pending = api.views.today({ view: 'today' });
  await settle();
  assert.equal(view.innerHTML, '', 'nothing paints over the page for a league the hero cannot serve');
  release();
  await pending;
  const withNfl = { ...cfbOnly, bets: [...cfbOnly.bets, mondayNfl] };
  let release2;
  const gate2 = new Promise(r => { release2 = r; });
  const next = loadApp('#today', { 'data/app/today.json': gate2 }, { hero: withNfl, stored: { 'kr:league': 'NFL' } });
  const pending2 = next.api.views.today({ view: 'today' });
  await settle();
  assert.match(next.view.innerHTML, /<h1>Next best bet · Mon 10\/12, 8:15 PM<\/h1>/);
  assert.match(next.view.innerHTML, /Monday Visitors at Hosts under 54\.5/);
  assert.match(next.view.innerHTML, /1 best bet for Monday, Oct 12 in NFL\./);
  assert.doesNotMatch(next.view.innerHTML, /Fixture State/, 'the college play stays out of an NFL first paint');
  release2();
  await pending2;
  await settle();
});
