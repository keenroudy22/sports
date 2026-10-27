'use strict';
/* The Kitchen Ticket Today (OWNER-DECISIONS 2026-10-07 item 22; DIRECTION-RULES section 5 as updated by it): the chef's
   line with the last game day's W-L, the first best bet hanging on the rail, the Climb stub, then (owner, 2026-10-07)
   every other section visible with no fold. today-hero.json paints the same top before today.json lands. */
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
  displayTitle: 'Fixture Receiver OVER 49.5 receiving yards', line: 49.5, projection: 61.2, direction: 'over', odds: -110, book: 'FanDuel',
  kickoff: '2026-10-10T20:00:00Z', expiresAt: '2026-10-10T19:00:00Z', featured: true, posted: true, status: 'active', cutoffOdds: -124,
  publishedAt: '2026-10-10T13:00:00Z', probabilityAtPublication: chance, modelLean: true, side: 'away',
  ticketWhy: 'I project 7.3 targets, AWY\'s top WR.', ticketBut: 'HOM\'s WR defense points against the over.',
  hitStrip: { v: [78, 94, 67, 26, 21], season: [3, 5], last10: [5, 10] },
};
const total = { ...prop, id: 'CFB-2026-W6-fixture-total-dk', kind: 'gamePicks', league: 'CFB', gameId: 'CFB-2', athleteId: null, position: null,
  market: null, marketType: 'total', displayTitle: 'Fixture State at Example Tech over 51.5', line: 51.5, odds: -105, side: null, hitStrip: null,
  ticketWhy: null, ticketBut: null, book: 'DraftKings', kickoff: '2026-10-10T23:00:00Z', expiresAt: '2026-10-10T22:00:00Z', featured: false, posted: false };
const laterOpen = { ...total, id: 'CFB-2026-W7-later-open-dk', displayTitle: 'Later Open at Somewhere under 44.5', line: 44.5, direction: 'under', cutoffLine: 44.5,
  kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z' };
const laterOff = { ...total, id: 'CFB-2026-W7-later-off-fd', displayTitle: 'Moved Line at Elsewhere under 56.5',
  kickoff: '2026-10-13T00:15:00Z', status: 'expired', entryNote: 'Closed to new entries at 11:45 AM ET: total moved 3 against, from 56.5 to 53.5.' };
const yesterday = { ...total, id: 'NFL-2026-W5-yesterday-dk', displayTitle: 'Graded Yesterday over 40.5', line: 40.5, kickoff: '2026-10-09T23:00:00Z',
  result: 'win', units: 0.95, posted: true, settledAt: '2026-10-10T03:00:00Z', actual: 'Visitors 24, Hosts 21' };
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
const PREP = { CFB: { day: '2026-10-10', rows: [
  { league: 'CFB', gameId: 'CFB-2', kickoff: total.kickoff, athleteId: '77', player: 'Prep Player', team: 'ARIZ', teamColor: '#cc0033', pos: 'WR',
    stat: 'recYds', direction: 'over', line: 54.5, odds: -114, book: 'FanDuel', hits: 6, games: 6, clears: true },
  { league: 'CFB', gameId: 'CFB-2', kickoff: total.kickoff, athleteId: '78', player: 'History Only', team: 'WVU', teamColor: '#002855', pos: 'RB',
    stat: 'rushYds', direction: 'over', line: 60.5, odds: -110, book: 'DraftKings', hits: 5, games: 6, clears: false }] } };
const TODAY = { generatedAt: '2026-10-10T13:50:00Z', games: GAMES, picks: [prop, total, laterOpen, laterOff, yesterday, ...rungs],
  season: SEASON, lastSlate: LAST, prep: PREP };
const HERO = {
  generatedAt: '2026-10-10T13:50:00Z', day: '2026-10-10', more: 0, season: SEASON, last: LAST,
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

test('a moneyline ticket shows the real price without treating win probability as a points projection', async () => {
  const ml={...prop,id:'NFL-ml',kind:'gamePicks',athleteId:null,position:null,market:null,
    marketType:'moneyline',direction:'away',side:'away',line:0,projection:.5,odds:130,
    displayTitle:'Fixture Away MONEYLINE',cutoffOdds:116,cutoffLine:0,cutoffBoundary:-.5,
    selectionPolicy:'2026-10-19-1u-2u',lane:'best_bet',riskUnits:1,hitStrip:null,
    ticketWhy:'The opposing defense has two starters out.',ticketBut:null,
    probabilityAtPublication:{chance:.458,breakEven:.435,edgePoints:2.3,calibrated:true},
    quote:{line:0,odds:130,observedAt:'2026-10-10T13:59:00Z'}};
  const hero={...HERO,bets:[{...ml,teams:{away:GAMES[0].away,home:GAMES[0].home}}]};
  const page=await loadApp('#record',{}, {hero,today:{...TODAY,picks:[ml]}}).api.views.today({view:'today'});
  assert.match(page,/Still good to \+116\./);
  assert.doesNotMatch(page,/Past my \+116/);
  assert.doesNotMatch(page,/Book (?:says|said)<b class="num">0(?:\.0)?<\/b>/);
  assert.doesNotMatch(page,/I (?:have|had) it at<b class="num">0\.5<\/b>/);
});
/* The top of Today: the chef's line, the first ticket and the Climb stub, up to the stub's aside. */
const top = page => page.slice(page.indexOf('<section class="kt-lede'), page.indexOf('<p class="kt-aside">'));
const mondayNfl = { ...prop, id: 'NFL-2026-W6-monday-total-dk', kind: 'gamePicks', athleteId: null, market: null, marketType: 'total',
  displayTitle: 'Monday Visitors at Hosts under 54.5', featured: false, kickoff: '2026-10-13T00:15:00Z', expiresAt: '2026-10-12T23:00:00Z' };
const cfbOnly = { ...HERO, bets: [HERO.bets[1]] };

test('the Climb status words still come from one function', () => {
  assert.equal(M.climbWords({ open: { step: 3 }, step: 3, settled: 2 }), 'Step 3 is live');
  assert.equal(M.climbWords({ step: 3, settled: 2, last: { result: 'win', step: 2 } }), 'Step 2 cashed · Step 3 not posted yet');
  assert.equal(M.climbWords({ step: 1, settled: 0 }), 'The first step waits for two clean games');
});

test('the first paint hangs only game-day bets on the rail, never future, moved or pulled plays', () => {
  const today = M.heroBets(HERO, NOW);
  assert.equal(today.today, true);
  assert.deepEqual(today.rows.map(r => r.id), [prop.id, total.id]);
  assert.deepEqual(M.heroBets(HERO, NOW, 'CFB').rows.map(r => r.id), [total.id]);
  const moved = { ...prop, id: 'moved-today', entryNote: 'Closed to new entries at 11:45 AM ET: moved.' };
  const pulled = { ...prop, id: 'pulled-today', entryNote: 'Pulled over news before its post went out.' };
  assert.deepEqual(M.heroBets({ bets: [moved, pulled, total] }, NOW).rows.map(r => r.id), [total.id], 'off the card and pulled stay off the rail');
  const next = M.heroBets({ bets: [laterOff, laterOpen, { ...laterOpen, id: 'later-day', kickoff: '2026-10-14T00:15:00Z' }] }, NOW);
  assert.equal(next.today, false);
  assert.deepEqual(next.rows.map(r => r.id), [], 'a later best bet is not recast as a bet for today');
  assert.deepEqual(M.heroBets({ bets: [yesterday] }, NOW).rows, []);
  assert.deepEqual(M.heroBets(null, NOW).rows, []);
  const nfl = M.heroBets({ bets: [...cfbOnly.bets, mondayNfl] }, NOW, 'NFL');
  assert.deepEqual([nfl.today, nfl.rows.map(r => r.id)], [false, []], 'a league filter does not make Monday a Saturday bet');
});

test('the first paint and the full card draw the same top, so nothing moves when today.json lands', async () => {
  let release;
  const gate = new Promise(r => { release = r; });
  const { api, view } = loadApp('#today', { 'data/app/today.json': gate });
  const pending = api.views.today({ view: 'today' });
  await settle();
  const first = view.innerHTML;
  assert.match(first, /class="hero-first kt-today"/);
  assert.match(first, /<p class="date">Saturday, Oct 10\. Friday results below\.<\/p><h1>Two for today\.<\/h1>/);
  assert.match(first, /Hot Plate \(POTD\)/);
  assert.match(first, /−110<\/b><i><\/i><b class="kt-book">FanDuel/, 'price and book are on the first paint');
  assert.match(first, /Today 4:00 PM/, 'kickoff is on the first paint');
  assert.match(first, /80\/20 Climb #2[\s\S]*Step 3[\s\S]*Not posted yet/, 'the Climb stub is on the first paint');
  release();
  const full = await pending;
  assert.doesNotMatch(full, /hero-first/);
  assert.equal(top(full), top(first), 'the chef\'s line, the first ticket and the Climb stub are identical on both paints');
  await settle();
});

test('Today keeps current sections visible and past tickets expandable; Off the card never hangs on the rail', async () => {
  const todayOff = { ...total, id: 'CFB-today-off-fd', displayTitle: 'Moved Line Today under 56.5', status: 'expired',
    entryNote: 'Closed to new entries at 11:45 AM ET: total moved 3 against, from 56.5 to 53.5.' };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [...TODAY.picks, todayOff] } });
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /aria-label="Today at a glance"[\s\S]*Best bets[\s\S]*80\/20 Climb/);
  assert.match(page, /Today’s best bets[\s\S]*Today’s Climb/);
  const at = text => { const i = page.indexOf(text); assert.ok(i >= 0, `missing ${text}`); return i; };
  const order = ['class="kt-lede', 'class="kt-pass"', 'class="kt-sec kt-climb"', 'class="kt-proof"', 'kt-nfl-now"', 'kt-bets"', 'class="kt-sec kt-left"', 'class="kt-sec kt-prep"',
    'kt-upsets"', 'kt-worth"', 'kt-games"', 'kt-off-card"', 'kt-community"', 'kt-sports"'].map(at);
  assert.deepEqual(order, order.slice().sort((a, b) => a - b), 'first screen -> tonight NFL -> future bets -> Leftovers -> Prep List -> research -> games -> off -> Discord -> sports');
  for (const gone of ['today-more', 'kt-fold', 'class="onboard"', 'today-status']) assert.ok(!page.includes(gone), gone);
  const folds = [...page.matchAll(/<details[^>]*data-box="([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(folds, ['climb-past', 'previous-results'], 'past Climb steps and previous results stay expandable');
  const rails = page.slice(0, at('class="kt-sec kt-left"'));
  assert.doesNotMatch(rails, /Moved Line at Elsewhere/, 'Off the card stays outside the rail');
  assert.match(page.slice(at('kt-off-card"')), /Off the card · 1<\/h2>[\s\S]*Moved Line Today/);
  const bets = page.slice(at('kt-bets"'), at('class="kt-sec kt-left"'));
  assert.match(bets, /<h2 class="kt-head" id="bets-h">More best bets<\/h2>/);
  assert.match(bets, /Example Tech/, 'today\'s other best bet stays on the page');
  assert.doesNotMatch(bets, /Later Open/, 'future bets stay off an active game day');
  assert.match(bets, /Still good to −124\./, 'each other best bet names its price limit, in the first ticket\'s words');
  assert.doesNotMatch(bets, /Still a bet down to|Best bets this season/, 'one limit sentence everywhere; the season record rides the first ticket and the season line only');
  assert.equal((page.match(/Best bets this season/g) || []).length, 1);
  assert.match(bets, /Book says<b class="num">51\.5<\/b>[\s\S]*I have it at<b class="num">61\.2<\/b>/,
    'and its useful model number against the book line');
  assert.doesNotMatch(bets, /kt-clip/, 'one chef, on the first rail only');
  assert.match(page, /Best Bets: 1–0<\/b> · \+0\.95u/, 'Same-category results carry their units');
  assert.match(page, /r-mark hit/);
  assert.match(page, /result Visitors 24, Hosts 21/);
  assert.match(page, /Past steps · 3/, 'every completed rung stays one tap away');
  assert.match(page, /Step 2 cashed\./);
  assert.match(page, /<p class="kt-proof"><a href="#record">Best Bets · <b class="num">35-35<\/b> · <span class="go">Every result ›<\/span><\/a><\/p>/, 'the fallback explicitly labels Best Bets before the full posted record lands');
  const discord = page.slice(at('kt-community"'));
  assert.match(discord, /Best bets land here about 10–15 minutes before X\.[\s\S]*discord\.gg\/ZnjubjsBPM[\s\S]*x\.com\/keenkooks/);
  assert.match(page.slice(at('kt-sports"')), /href="#today\?sport=NBA">NBA →/);
});

test('an NFL game today stays prominent and a later best bet stays off Today', async () => {
  const future = [laterOpen, { ...laterOpen, id: 'later-more', kickoff: '2026-10-14T00:15:00Z' }];
  const nightGame = { ...GAMES[0], kickoff: '2026-10-11T00:15:00Z', v2: { away: 23.2, home: 26.9, total: 50.1, margin: 3.7, winProb: 0.61 }, market: { spread: -8.5, total: 48.5 } };
  const games = [nightGame, GAMES[1]];
  const page = await loadApp('#record', {}, { today: { ...TODAY, picks: future, games } }).api.views.today({ view: 'today' });
  const spot = page.slice(page.indexOf('kt-nfl-now"'), page.indexOf('kt-upsets"'));
  assert.ok(page.indexOf('kt-climb"') < page.indexOf('kt-nfl-now"'));
  assert.match(spot, /Tonight&#39;s NFL|Tonight's NFL/);
  assert.match(spot, /href="#game\/NFL-1"[\s\S]*Visitors[\s\S]*Hosts/);
  assert.match(spot, /Total 50\.1[\s\S]*48\.5/, 'the spotlight has the projection and book line');
  assert.match(spot, /Matchup and lines · not a best bet/);
  assert.doesNotMatch(spot, /href="#game\/CFB-2"/, 'other games remain in the full games section');
  assert.equal((page.match(/class="proj[^"]*" href="#game\/NFL-1"/g) || []).length, 1, 'the spotlighted game appears only once on Today');
  assert.match(page, /<h2 class="kt-head" id="games-h">Other games today<\/h2>/, 'remaining games have their own heading');
  assert.doesNotMatch(page, /Upcoming best bets|Later Open/, 'future tickets are not mixed into an active game day');
  const cfb = await loadApp('#today?sport=CFB', {}, { today: { ...TODAY, picks: future, games } }).api.views.today({ view: 'today', league: 'CFB' });
  assert.doesNotMatch(cfb, /kt-nfl-now/, 'saved college-only view does not leak the NFL card');
});

test('the Prep List shows only the rows the build chose, with the price check only where it clears', async () => {
  const { api } = loadApp('#record');
  const page = await api.views.today({ view: 'today' });
  const prep = page.slice(page.indexOf('class="kt-sec kt-prep"'), page.indexOf('kt-upsets"'));
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
  assert.match(first, /Book says<b class="num">49\.5<\/b><\/span><i><\/i><span>I have it at<b class="num">61\.2<\/b>/);
  assert.doesNotMatch(first, /%|price needs/);
  assert.match(first, /<span class="kt-tag">WHY<\/span><span>I project 7\.3 targets, AWY&#39;s top WR\.<\/span>/);
  assert.match(first, /<span class="kt-tag">BUT<\/span><span>HOM&#39;s WR defense points against the over\.<\/span>/);
  assert.match(first, /Still good to −124\./);
  assert.match(first, /Best bets this season<b class="num">35-35<\/b>/);
  assert.match(first, /3 of 5 this season<\/b>5 of his last 10/);
  for (const banned of ['Price matching our chance', 'Chance vs price', ' pts', 'fair', 'edge']) assert.ok(!first.includes(banned), banned);
  const text = first.replace(/<[^>]+>/g, ' ').replace(/&#\d+;/g, "'");
  /* 6 and 0: the kickoff countdown ("Kicks off in 6h 0m"), restored on 2026-10-07. */
  const allowed = new Set(['49.5', '61.2', '110', '7.3', '124', '35', '35', '78', '94', '67', '26', '21', '3', '5', '5', '10', '4', '00', '1', '2', '6', '0']);
  assert.match(first, /<p class="kt-cd">Kicks off in 6h 0m<\/p>/);
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
  assert.match(raw, /Book says[\s\S]*I have it at/, 'the plain model number does not depend on a public percentage');
  assert.doesNotMatch(raw, /%|price needs/);
  const aged = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z' });
  assert.match(aged, /Posted price may be gone\. Check your book\./);
  assert.match(aged, /I had it at/);
  assert.doesNotMatch(aged, /Still good to|I have it at/);
});

test('partial Today history never replaces the complete hero Climb balance', async () => {
  const page = await loadApp('#record', {}, { today: { ...TODAY, picks: [prop, rungs[2]] } }).api.views.today({ view: 'today' });
  assert.match(page, /80\/20 Climb #2[\s\S]*Step 3/);
  assert.doesNotMatch(page, /80\/20 Climb number 1,/);
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

test('a saved league filter does not flash a future bet as today while the game-day feed loads', async () => {
  const { api: empty } = loadApp('#today', {}, { hero: cfbOnly, stored: { 'kr:league': 'NFL' } });
  assert.equal(empty.firstPaint(cfbOnly), '');
  const withNfl = { ...cfbOnly, bets: [...cfbOnly.bets, mondayNfl] };
  let release;
  const gate = new Promise(r => { release = r; });
  const next = loadApp('#today', { 'data/app/today.json': gate }, { hero: withNfl, today: { ...TODAY, picks: [mondayNfl], games: GAMES }, stored: { 'kr:league': 'NFL' } });
  const pending = next.api.views.today({ view: 'today' });
  await settle();
  assert.doesNotMatch(next.view.innerHTML, /One for Monday|Monday Visitors at Hosts/);
  assert.doesNotMatch(next.view.innerHTML, /Fixture State/);
  release();
  await pending;
  await settle();
  assert.match(next.view.innerHTML, /<h1>Nothing cleared my bar today\.<\/h1>/);
  assert.doesNotMatch(next.view.innerHTML, /Upcoming best bets|Monday Visitors at Hosts under 54\.5/);
  assert.doesNotMatch(next.view.innerHTML, /NFL only/, 'bare Today resets a stale saved NFL-only filter');
  assert.doesNotMatch(next.view.innerHTML, /Fixture State/);
});

test('bare Today starts with all football; a sport URL stays an explicit choice', async () => {
  const all = loadApp('#today', {}, { stored: { 'kr:league': 'NFL' } });
  all.api.render();
  await settle();
  assert.match(all.view.innerHTML, /Two for today/, 'college is not hidden by yesterday’s NFL filter');
  assert.doesNotMatch(all.view.innerHTML, /NFL only/);
  const nfl = loadApp('#today?sport=NFL', {}, { stored: { 'kr:league': 'CFB' } });
  nfl.api.render();
  await settle();
  assert.match(nfl.view.innerHTML, /NFL only · <a href="#today\?sport=ALL">See all sports ›<\/a>/);
  assert.doesNotMatch(nfl.view.innerHTML, /Fixture State at Example Tech/);
});

test('an active game day never mixes in a later ticket or future-slate card', async () => {
  const sunday = { ...GAMES[0], id: 'NFL-SATURDAY', kickoff: '2026-10-10T17:00:00Z' };
  const monday = { ...GAMES[0], id: 'NFL-MONDAY', kickoff: '2026-10-13T00:15:00Z' };
  const bills = { ...laterOpen, league: 'NFL', gameId: 'NFL-MONDAY', kickoff: monday.kickoff, displayTitle: 'Bills at Rams under 54.5' };
  const page = await loadApp('#today?sport=NFL', {}, { today: { ...TODAY, picks: [bills], games: [sunday, monday] } }).api.views.today({ view: 'today', league: 'NFL' });
  assert.doesNotMatch(page, /Next football|Upcoming best bets|Bills at Rams under 54\.5|Monday, Oct 12/);
  assert.match(page, /Today(?:'|&#39;)s NFL/);
});

test('an off-day may show clearly labeled future prep', async () => {
  const sunday = { ...GAMES[0], id: 'NFL-SUNDAY', kickoff: '2026-10-11T17:00:00Z' };
  const bills = { ...laterOpen, league: 'NFL', gameId: 'NFL-SUNDAY', kickoff: sunday.kickoff, displayTitle: 'Bills at Rams under 54.5' };
  const page = await loadApp('#today?sport=NFL', {}, { today: { ...TODAY, picks: [bills], games: [sunday] } }).api.views.today({ view: 'today', league: 'NFL' });
  assert.match(page, /Next football[\s\S]*Sunday, Oct 11/);
  assert.match(page, /Upcoming best bets[\s\S]*Bills at Rams under 54\.5/);
});

test('with nothing on the card the rail does not reveal desk timing', async () => {
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [yesterday, ...rungs] } });
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /<h1>Nothing cleared my bar today\.<\/h1>/);
  assert.match(page, /class="kt-hook h1"[\s\S]*class="kt-hook h2"/);
  assert.match(page, /Nothing cleared my bar today\./);
  assert.match(page, /No best bet today\. Tonight's games are below\./);
  assert.doesNotMatch(page, /I look again|desk run|11:45 AM/i);
  assert.doesNotMatch(page, /<article class="kt-order/, 'no blank ticket and no forced pick');
});

test('the compact prior-day recap lists every win and loss without truncation', async () => {
  const day = (i, result) => ({ ...yesterday, id: `NFL-2026-W5-day-${i}`, result, kickoff: `2026-10-09T${10 + i}:00:00Z` });
  const settled = [day(1, 'loss'), day(2, 'win'), day(3, 'win'), day(4, 'win'), day(5, 'win'), day(6, 'win'), day(7, 'loss')];
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [prop, ...settled, ...rungs], lastSlate: { ALL: { day: '2026-10-09', wins: 5, losses: 2, pushes: 0 } } } });
  const page = await api.views.today({ view: 'today' });
  const left = page.slice(page.indexOf('class="kt-sec kt-left"'), page.indexOf('class="kt-sec kt-prep"'));
  assert.equal((left.match(/r-mark miss/g) || []).length, 2, 'both misses stay');
  assert.equal((left.match(/class="receipt"/g) || []).length, 7, 'all seven posted tickets remain available');
  assert.match(left, /<details class="plain-fold" data-box="previous-results"><summary>See all 7 tickets<\/summary>/);
  assert.doesNotMatch(left, /<details[^>]*\bopen\b/, 'past tickets start collapsed');
  assert.doesNotMatch(left, /more on the record/);
  assert.match(left, /Best Bets: 5–2/);
});

test('Today reconciles its last-slate headline and slips to released plays only', async () => {
  const released = { ...yesterday, id: 'CFB-2026-W6-nevada-utep-over-49-5-dk',
    displayTitle: 'Nevada/UTEP over 49.5', kickoff: '2026-10-09T23:25:00Z', result: 'loss',
    units: -1, posted: true, actual: 'Nevada 30, UTEP 13' };
  const hidden = name => ({ ...released, id: `hidden-${name}`, displayTitle: name,
    posted: false, delivery: null });
  const gut = { ...released, id: 'released-gut', displayTitle: 'Released Gut call hit',
    lane: 'gut_call', result: 'win', units: 0.5 };
  const page = await loadApp('#record', {}, { today: { ...TODAY,
    picks: [prop, released, gut, hidden('Arizona at West Virginia'), hidden('SDSU at Oregon State'), ...rungs],
    lastSlate: { ALL: { day: '2026-10-10', wins: 0, losses: 1, pushes: 0, units: -1 } } } }).api.views.today({ view: 'today' });
  const left = page.slice(page.indexOf('class="kt-sec kt-left"'), page.indexOf('class="kt-sec kt-prep"'));
  assert.match(left, /Best Bets: 0–1<\/b> · −1\.00u/);
  assert.match(left, /Other straights: 1–0<\/b> · \+0\.50u/);
  assert.match(left, /Nevada\/UTEP over 49\.5/);
  assert.match(left, /Released Gut call hit/);
  assert.doesNotMatch(left, /Arizona at West Virginia|SDSU at Oregon State/);
});

test('the browser shell requests the core build that exports the shared headline counter', () => {
  const index = fs.readFileSync('site/index.html', 'utf8');
  const hash = require('node:crypto').createHash('sha256').update(fs.readFileSync('site/core.js')).digest('hex').slice(0,12);
  assert.ok(index.includes(`core.js?v=sha256-${hash}`));
  assert.equal(typeof C.chefRecord, 'function');
  assert.equal(typeof C.isHeadline, 'function');
});

test('new tiers show1u and2u consistently while legacy Full Sends retain their stake', async () => {
  for (const [lane, riskUnits, label] of [['best_bet',1,'Best Bet · 1u'],['chef_pick',2,"Chef&#39;s Pick · 2u"],['best_bet',.5,'Best Bet · 0.5u'],['chef_pick',1,"Chef&#39;s Pick · 1u"],['gut_call',.5,'Full Send']]) {
    const pick={...prop,lane,riskUnits,featured:true,
      ...(lane==='gut_call'?{}:{selectionPolicy:'2026-10-19-1u-2u'})};
    if(lane==='gut_call') pick.featured=false;
    const {api}=loadApp('#record',{}, {today:{...TODAY,picks:[pick]}});
    const page=await api.views.pick({id:pick.id});
    assert.ok(page.includes(label),label);
    assert.ok(page.includes(`Graded at the posted ${riskUnits}u stake`));
  }
});

test('a future Chef loss refunded by a book still explains the actual two-unit headline stake', async () => {
  const pick={...prop,lane:'chef_pick',riskUnits:2,result:'loss',earlyExit:true,units:0,
    selectionPolicy:'2026-10-19-1u-2u'};
  const {api}=loadApp('#record',{}, {today:{...TODAY,picks:[pick]}});
  const page=await api.views.pick({id:pick.id});
  assert.match(page,/headline record still counts it as −2u/);
  assert.doesNotMatch(page,/counts it as −1u/);
});

test('Today prints a settled player name and full stat line, never the stored athlete id', async () => {
  const king = { ...yesterday, id: 'CFB-2026-W6-king-over-49-5-recyds-dk', league: 'CFB',
    title: 'TK King OVER 49.5 receiving yards', displayTitle: 'TK King OVER 49.5 receiving yards',
    player: 'TK King', athleteId: '4869443', marketType: 'prop', market: 'recYds',
    result: 'loss', actual: '4869443: 0 receiving yards',
    resultDetail: '0 catches on 6 targets, 0 yards · missed by 49.5' };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [prop, king, ...rungs],
    lastSlate: { ALL: { day: '2026-10-09', wins: 0, losses: 1, pushes: 0 } } } });
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /TK King · 0 catches on 6 targets, 0 yards · missed by 49\.5/);
  assert.doesNotMatch(page, /4869443: 0 receiving yards/);
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
    assert.match(t, /<p class="kt-now">Projection unavailable\.<\/p>/);
    assert.doesNotMatch(t, /under review|checking.*role/i);
    assert.match(t, /class="kt-order[^"]*is-held/);
    for (const banned of ['Still good', 'I have it', 'I had it', 'kt-chance', 'kt-orderup', 'Now −', '56.0%', 'I project', '7.3 targets']) assert.ok(!t.includes(banned), banned);
    assert.match(t, /<span class="kt-tag">BUT<\/span><span>HOM&#39;s WR defense points against the over\.<\/span>/, 'a counterpoint with no projection stays');
    assert.ok(!t.includes('<span class="kt-tag">WHY</span>'), 'the projection WHY is left off, never swapped for a later saved line');
    assert.match(t, /−110<\/b><i><\/i><b class="kt-book">FanDuel/, 'the posted price and book stay');
  }
  assert.equal(first, firstTicket(full), 'both paints say the same thing');
});

test('a play held only by its board rows drops a projection WHY on Today and the play page (the game page draws the same ticket)', async () => {
  const today = { ...TODAY, picks: [prop, total, ...rungs] };
  const { api } = loadApp('#record', {}, { today, extra: linesFor([kingRow]) });
  await api.views.today({ view: 'today' });
  await settle();
  const pages = [firstTicket(await api.views.today({ view: 'today' })), await api.views.pick({ id: prop.id })];
  for (const page of pages) {
    assert.match(page, /Projection unavailable\./);
    assert.ok(!page.includes('I project'), 'no held projection in WHY');
    assert.ok(!page.includes('7.3 targets'));
  }
  const clean = await loadApp('#record', {}, { today }).api.views.pick({ id: prop.id });
  assert.match(clean, /<span class="kt-tag">WHY<\/span><span>I project 7\.3 targets/, 'an unheld play keeps its saved WHY');
});

test('a play held after Discord delivery keeps its posted Hot Plate, historical chance and WHY', async () => {
  const delivered = { ...prop, held: { kind: 'qb', afterPosting: true },
    delivery: { discordAt: '2026-10-10T16:00:00Z' },
    quote: { odds: -104, line: 49.5, observedAt: '2026-10-10T13:37:35Z' } };
  const today = { ...TODAY, picks: [delivered, total, ...rungs] };
  const { api } = loadApp('#today', {}, { today, hero: { ...HERO, bets: [delivered] }, extra: linesFor([kingRow]) });
  const ticket = firstTicket(await api.views.today({ view: 'today' }));
  assert.match(ticket, /Hot Plate \(POTD\)/);
  assert.match(ticket, /Book said/);
  assert.match(ticket, /I had it at/);
  assert.doesNotMatch(ticket, /price needed|%/);
  assert.match(ticket, /quarterback picture changed since I posted/);
  assert.match(ticket, /Latest −104/);
  assert.match(ticket, /<span class="kt-tag">WHY<\/span><span>I project 7\.3 targets/);
  assert.doesNotMatch(ticket, /Under review|ORDER UP/);
  const page = await api.views.pick({ id: delivered.id });
  assert.match(page, /I posted this at 12:00 PM at −110 at FanDuel/);
  assert.match(page, /It still counts at that price/);
  assert.doesNotMatch(page, /<h2 class="kt-tape">My price<\/h2>/);
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
  assert.match(first, /Now 49.5 at −115 at 9:20 AM\. Still good to −124\./);
  assert.match(first, /I have it at/);
  assert.equal(first, full);
  const stale = { ...aged, quote: { ...aged.quote, observedAt: '2026-10-10T09:00:00Z' } };
  const { api: a2 } = loadApp('#record', {}, { today: { ...TODAY, picks: [stale, ...rungs] } });
  const t = firstTicket(await a2.views.today({ view: 'today' }));
  assert.match(t, /Posted price may be gone\. Check your book\./, 'older than four hours at view time: the browser drops it');
  assert.match(t, /I had it at/);
});

test('an expired quote never wears ORDER UP unless a fresh same-book price is still inside the limit', async () => {
  const ticketOf = async pick => { const page = await loadApp('#record', {}, { today: { ...TODAY, picks: [pick, ...rungs] } }).api.views.today({ view: 'today' });
    return page.slice(page.indexOf('<article class="kt-order'), page.indexOf('</article>')); };
  const aged = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z' });
  assert.match(aged, /Posted price may be gone/);
  assert.doesNotMatch(aged, /kt-orderup|ORDER UP/, 'an expired quote never reads as open');
  const moved = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z', quote: { odds: -130, line: 49.5, observedAt: '2026-10-10T13:20:00Z' } });
  assert.match(moved, /Past my −124 limit\./);
  const changedLine = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z', cutoffBoundary: 51.5, quote: { odds: -108, line: 53.5, observedAt: '2026-10-10T13:20:00Z' } });
  assert.match(changedLine, /Now 53.5 at −108/);
  assert.match(changedLine, /Line moved from 49.5; outside my posted range/);
  assert.doesNotMatch(changedLine, /Past my|kt-orderup/);
  assert.doesNotMatch(moved, /kt-orderup/, 'a fresh price past the limit is not open either');
  const inside = await ticketOf({ ...prop, expiresAt: '2026-10-10T12:00:00Z', quote: { odds: -115, line: 49.5, observedAt: '2026-10-10T13:20:00Z' } });
  assert.match(inside, /Still good to −124\./);
  assert.match(inside, /kt-orderup/, 'a fresh same-book price inside the limit is still live');
  assert.match(await ticketOf(prop), /kt-orderup/, 'an open quote does');
});

test('a settled ticket never wears ORDER UP', async () => {
  const { api } = loadApp('#record', {}, { today: TODAY, extra: {} });
  const page = await api.views.pick({ id: yesterday.id });
  assert.match(page, /kt-stamp hit/);
  assert.doesNotMatch(page, /kt-orderup|ORDER UP/);
  const open = await loadApp('#record').api.views.pick({ id: prop.id });
  assert.match(open, /ORDER UP/, 'an open best bet does');
});

test('an off-card published play never becomes a claim that nothing was posted', async () => {
  const closed = { ...prop, entryNote: 'Closed to new entries at 9:00 AM ET: line moved.' };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, generatedAt:'2026-10-10T14:00:00Z', picks: [closed, ...rungs] } });
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /Earlier posted plays and their original prices remain/);
  assert.doesNotMatch(page, /No official best bet yet|No best bet today|Nothing cleared my bar today/);
});

test('the play page under review shows no fair price, edge, chance or projection, and keeps the posted price', async () => {
  const king = { ...prop, held: KING_HOLD, projection: 68.2, cutoff: 'Good to −124 at 49.5.', why: 'Our model projects 68.2.',
    probabilityAtPublication: { chance: 0.537, rawChance: 0.659, calibration: 0.23, calibrationN: 398, breakEven: 0.505, edgePoints: 3.2, calibrated: true } };
  const { api } = loadApp('#record', {}, { today: { ...TODAY, picks: [king, ...rungs] }, extra: linesFor([kingRow]) });
  const page = await api.views.pick({ id: king.id });
  assert.match(page, /<h2 class="kt-tape">The hold<\/h2>/);
  assert.match(page, /UNAVAILABLE/);
  assert.match(page, /No usable projection: the quarterback role is not established in the model\./);
  assert.match(page, /graded at −110 at FanDuel, the price we posted/);
  for (const banned of ['My price', 'How we got', 'projects', 'I project', '7.3 targets', '68.2', '53.7%', '65.9%', '+3.2', '−116', 'Still good', 'Still a bet down to', 'I have it', 'Price we would still play', 'Our notes when we posted'])
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
  const settled = { ...rungs[2], why: 'Ladder step 2: two easier player lines. $75 rides with $19 banked. A win returns $117.' };
  const page2 = await loadApp('#record', {}, { today: { ...TODAY, picks: [prop, rungs[0], rungs[1], settled] } }).api.views.pick({ id: settled.id });
  assert.match(page2, /<h2 class="kt-tape">The stake<\/h2><p>Ladder step 2: two easier player lines\. \$75 rides with \$19 banked\. A win returns \$117\./,
    'a settled rung whose words were saved as why keeps them too');
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

/* ---------- the 2026-10-07 restore: what the old Today showed, back on the page without a tap ---------- */
test('the countdown and the share-card link show only before kickoff and only for a card path the build named', async () => {
  const card = 'data/cards/NFL-2026-W5-fixture-rec-fd-potd.png';
  const withCard = path => ({ ...HERO, bets: [{ ...HERO.bets[0], card: path }, HERO.bets[1]] });
  const firstOf = page => page.slice(page.indexOf('<article class="kt-order'), page.indexOf('</article>'));
  const shown = firstOf(await loadApp('#record', {}, { hero: withCard(card) }).api.views.today({ view: 'today' }));
  assert.match(shown, /<p class="kt-cd">Kicks off in 6h 0m · <a href="data\/cards\/NFL-2026-W5-fixture-rec-fd-potd\.png" target="_blank" rel="noopener">See the card ↗<\/a><\/p>/);
  for (const bad of [null, 'data/cards/../secret.png', 'https://example.com/x.png', 'data/cards/x.jpg']) {
    assert.doesNotMatch(firstOf(await loadApp('#record', {}, { hero: withCard(bad) }).api.views.today({ view: 'today' })), /See the card/, String(bad));
  }
  const started = { ...prop, kickoff: '2026-10-10T13:30:00Z', expiresAt: '2026-10-10T13:00:00Z' };
  const after = await loadApp('#record', {}, { today: { ...TODAY, picks: [started, total, ...rungs] } }).api.views.today({ view: 'today' });
  assert.doesNotMatch(after.slice(0, after.indexOf('kt-bets"')), /kt-cd|Kicks off/, 'no countdown once the game has kicked off');
  const page = await loadApp('#record').api.views.today({ view: 'today' });
  const later = page.slice(page.indexOf('Later Open at Somewhere') - 1600, page.indexOf('Later Open at Somewhere'));
  assert.doesNotMatch(later.slice(later.lastIndexOf('<article')), /Kicks off/, 'no countdown more than a day out');
});

test('the season line uses the same record math as the Record page once every play has loaded', async () => {
  const { api } = loadApp('#record');
  await api.views.today({ view: 'today' });
  await settle();
  const page = await api.views.today({ view: 'today' });
  const k = api.moreContext().kpiStrip(TODAY.picks, null);
  const archive = C.recordArchive(TODAY.picks), rec = C.recordBreakdown(archive.rows.filter(p => !C.isParlay(p)));
  assert.equal(k.rec.captured.units, rec.captured.units);
  const posted = archive.rows.filter(p => C.countsPublic(p) && !C.isLadder(p) && !C.isUnpricedImport(p));
  const all = C.summaryOf(posted), u = C.summaryOf(posted.filter(p => !p.priceAssumed)).units;
  const units = `${u > 0 ? '+' : u < 0 ? '−' : ''}${Math.abs(u).toFixed(2)} units`;
  assert.ok(page.includes(`<p class="kt-proof"><a href="#record">All posted football plays · <b class="num">${all.wins}-${all.losses}</b> · <span class="pos">${units}</span> at posted prices · <span class="go">Every result ›</span></a></p>`),
    page.slice(page.indexOf('kt-proof'), page.indexOf('kt-proof') + 240));
});

test('Today merges settled personal tickets once and reconciles all five prior-day plays to the calendar', async () => {
  const base = {...yesterday, kickoff:'2026-10-09T23:00:00Z',posted:true,season:2026};
  const official=[{...base,id:'best',lane:'best_bet',result:'loss',units:-1},
    {...base,id:'full',lane:'gut_call',result:'loss',units:-.5}];
  const personal=(id,result,units,kind='parlays')=>({...base,id,displayTitle:id,community:true,lane:'personal',
    kind,legs:kind==='parlays'?[{},{}]:[],parlayType:kind==='parlays'?'community':null,result,units,
    riskUnits:.2,card:`img/tickets/${id}.png`});
  const community=[personal('Q1 receiving parlay','win',2.986),personal('Eight-leg parlay','win',1.373),
    personal('Juszczyk first TD','loss',-.1,'props')];
  const today={...TODAY,picks:official,historyFile:'record.json'};
  const {api}=loadApp('#record',{}, {today,extra:{'data/app/record.json':{picks:official,communityPicks:community}}});
  await api.views.today({view:'today'});await settle();
  const page=await api.views.today({view:'today'});
  const left=page.slice(page.indexOf('class="kt-sec kt-left"'),page.indexOf('class="kt-sec kt-prep"'));
  assert.match(left,/Best Bets: 0–1<\/b> · −1\.00u/);
  assert.match(left,/Other straights: 0–1<\/b> · −0\.50u/);
  assert.match(left,/My Card: 2–1<\/b> · \+4\.26u/);
  assert.equal((left.match(/class="receipt"/g)||[]).length,5);
  for(const p of community)assert.ok(left.includes(p.displayTitle));
  assert.match(left,/\+2\.99u/);assert.match(left,/\+1\.37u/);assert.match(left,/−0\.10u/);
  assert.ok(left.includes('img/tickets/Eight-leg parlay.png'));
});

const UPSET = { team: 'Arizona', opponent: 'West Virginia', odds: 150, opponentOdds: -180, modelChance: 0.53, marketChanceNoVig: 0.38, book: 'draftkings',
  observedAt: '2026-10-10T13:30:00Z', reasons: ['Our score has Arizona 27.1, West Virginia 24.0 — Arizona by 3.1', 'Arizona rates better on defense'],
  warnings: ['Raw model estimate, not a calibrated value bet'] };
test('Underdog watch is its own visible research section: outright upsets apart from spread covers, never a best bet', async () => {
  const games = [GAMES[0], { ...GAMES[1], upsetWatch: UPSET }];
  const page = await loadApp('#record', {}, { today: { ...TODAY, games } }).api.views.today({ view: 'today' });
  const sec = page.slice(page.indexOf('kt-upsets"'), page.indexOf('kt-worth"'));
  assert.match(sec, /<h2 class="kt-tape" id="upsets-h">Underdog watch<\/h2><span class="kt-kind">Upset research, not best bets<\/span>/);
  assert.match(sec, /Arizona · \+150 to win outright<\/b><\/a> <span class="badge research">Top upset signal<\/span>/);
  assert.match(sec, /We give them 53% to win\. Vegas has them at 38% once you take out the book&#39;s cut\. At \+150 you need 40\.0% to profit\./);
  assert.match(sec, /Our score has Arizona 27\.1, West Virginia 24\.0/, 'the projected score');
  assert.match(sec, /DraftKings · other team −180|DraftKings · other team -180/);
  assert.match(sec, /price checked/);
  assert.match(sec, /Outright upset candidates[\s\S]*Underdog spreads: none highlighted right now\./, 'spread covers stay a separate line');
  for (const bad of ['kt-order', 'Best bet', 'ORDER UP', 'Hot Plate']) assert.ok(!sec.includes(bad), bad);
  const none = await loadApp('#record').api.views.today({ view: 'today' });
  assert.match(none.slice(none.indexOf('kt-upsets"'), none.indexOf('kt-worth"')), /No current outright-upset or underdog-spread highlight\./, 'the honest empty state stays');
});

test('Today never promotes a future-day upset candidate', async () => {
  const future = { ...GAMES[1], id: 'CFB-future', kickoff: '2026-10-17T19:30:00Z', upsetWatch: UPSET };
  const page = await loadApp('#record', {}, { today: { ...TODAY, games: [GAMES[0], future] } }).api.views.today({ view: 'today' });
  const sec = page.slice(page.indexOf('kt-upsets"'), page.indexOf('kt-worth"'));
  assert.doesNotMatch(sec, /Arizona · \+150/);
  assert.match(sec, /No current outright-upset or underdog-spread highlight\./);
});

/* Board rows for Worth a look: fresh, open, priced, graded. */
const OBS = '2026-10-10T13:40:00Z';
const lineRow = (id, extra = {}, grade = {}) => ({ id, league: 'NFL', gameId: 'NFL-1', kickoff: prop.kickoff, state: 'open', odds: -110, book: 'draftkings',
  observedAt: OBS, title: `${id} over 44.5`, marketType: 'total', direction: 'over', line: 44.5,
  grade: { calibrated: true, view: 'lean', chance: 0.58, needs: 0.524, edge: 5, ...grade }, ...extra });
const LINES = [
  lineRow('A-total', {}, { edge: 6 }),
  lineRow('A-total-alt', { line: 45.5, title: 'A-total-alt over 45.5' }, { edge: 4 }),
  lineRow('B-prop', { athleteId: '50', player: 'Board Receiver', stat: 'recYds', marketType: null, title: 'Board Receiver over 60.5 receiving yards', line: 60.5 }, { edge: 3 }),
  lineRow('C-spread', { league: 'CFB', gameId: 'CFB-2', kickoff: total.kickoff, marketType: 'spread', direction: 'away', title: 'ARIZ +6.5', line: 6.5 }, { edge: 2.5 }),
  lineRow('D-thin', { gameId: 'CFB-2', league: 'CFB', kickoff: total.kickoff }, { edge: 9, thin: true }),
  lineRow('E-raw', { athleteId: '51', stat: 'rec', marketType: null, player: 'Raw Guy' }, { edge: 8, calibrated: false }),
  lineRow('F-on-card', { athleteId: '9', stat: 'recYds', marketType: null, player: 'Fixture Receiver', line: 49.5 }, { edge: 7 }),
  lineRow('G-small', { athleteId: '52', stat: 'rushYds', marketType: null, player: 'Small Edge' }, { edge: 1 }),
];
test('Today research favors props, then sides, then one total; held and posted lines stay out', async () => {
  const now = NOW;
  const vms = LINES.map(r => M.lineVM(r, now));
  const official = new Set([M.officialKey(prop)]);
  assert.deepEqual(M.worthRows(vms, official).map(r => r.id), ['B-prop', 'G-small', 'C-spread']);
  const otherTotal = M.lineVM(lineRow('H-other-total', { gameId: 'NFL-2' }, { edge: 20 }), now);
  assert.deepEqual(M.worthRows([otherTotal, ...vms], official).map(r => r.id),
    ['B-prop', 'G-small', 'C-spread'], 'a total cannot crowd props or sides off Today');
  assert.deepEqual(M.worthRows([otherTotal, ...vms.filter(vm => vm.id !== 'G-small')], official).map(r => r.id),
    ['B-prop', 'C-spread', 'H-other-total'], 'when a slot remains, only the top total appears');
  assert.deepEqual(M.todayResearchOrder([
    { id: 'total-a', marketType: 'total', hits: 10, games: 10 },
    { id: 'side', marketType: 'spread', hits: 7, games: 10 },
    { id: 'prop', stat: 'recYds', hits: 6, games: 10 },
    { id: 'total-b', marketType: 'total', hits: 9, games: 10 },
  ], 3, (a, b) => b.hits / b.games - a.hits / a.games).map(r => r.id),
  ['prop', 'side', 'total-a'], 'the Prep List uses the same category order and one-total cap');
  const held = M.lineVM(lineRow('H-held', { athleteId: '53', stat: 'recYds', marketType: null, roleSuspect: true }, { edge: 12 }), now);
  assert.ok(!M.worthRows([held, ...vms], official).some(r => r.id === 'H-held'), 'a role or price hold never shows as research worth a look');
  const files = { 'data/app/lines.json': { files: { NFL: 'lines-NFL.json', CFB: 'lines-CFB.json' } },
    'data/app/lines-NFL.json': { league: 'NFL', lines: LINES.filter(r => r.league === 'NFL') }, 'data/app/lines-CFB.json': { league: 'CFB', lines: LINES.filter(r => r.league === 'CFB') } };
  const { api } = loadApp('#record', {}, { extra: files });
  await api.views.today({ view: 'today' });
  await settle();
  const page = await api.views.today({ view: 'today' });
  const sec = page.slice(page.indexOf('kt-worth"'), page.indexOf('kt-games"'));
  assert.match(sec, /<h2 class="kt-tape" id="worth-h">Research worth a look<\/h2><span class="kt-kind">Not best bets<\/span>/);
  assert.match(sec, /Board Receiver over 60\.5[\s\S]*G-small over 44\.5[\s\S]*ARIZ \+6\.5/);
  for (const out of ['D-thin', 'E-raw', 'F-on-card', 'A-total', 'A-total-alt']) assert.ok(!sec.includes(out), out);
  assert.match(sec, /58% our chance · 52% needed/);
  assert.match(sec, /href="#research\/lines">See every line ›/);
});

test('an empty official rail names the strongest current look and the exact reason it is not a play', async () => {
  const closest = lineRow('Closest Look', { athleteId: '88', player: 'Closest Look', stat: 'recYds', marketType: null,
    title: 'Closest Look over 42.5 receiving yards', line: 42.5 }, { view: 'pass', tier: 'pass', chance: 0.53, needs: 0.524, edge: 0.6 });
  const raw = lineRow('Raw Look', { athleteId: '89', player: 'Raw Look', stat: 'rec', marketType: null },
    { calibrated: false, view: 'pass', tier: 'pass', chance: 0.61, edge: 8 });
  const files = linesFor([closest, raw]);
  const emptyToday = { ...TODAY, picks: [yesterday, ...rungs] };
  const { api } = loadApp('#today', {}, { today: emptyToday, hero: { ...HERO, bets: [] }, extra: files });
  await api.views.today({ view: 'today' });
  await settle();
  const page = await api.views.today({ view: 'today' });
  assert.match(page, /<h1>Here’s what I like most today\.<\/h1>/);
  assert.match(page, /No official best bet yet\. My strongest current look is below\./);
  const favorite = page.slice(page.indexOf('kt-favorite"'), page.indexOf('class="kt-sec kt-climb"'));
  assert.match(favorite, /What I like most/);
  assert.match(favorite, /Strongest current lean · not a best bet/);
  assert.match(favorite, /Closest Look over 42\.5 receiving yards/);
  assert.match(favorite, /Why it is not an official play:<\/b> It is positive value by 0\.6 points, but it still needs a strong verified reason and the final release checks before I call it Full Send\./);
  assert.doesNotMatch(favorite, /Raw Look/);
  assert.equal((page.match(/Closest Look over 42\.5 receiving yards/g) || []).length, 1, 'the favorite is not repeated in Research worth a look');
});

test('the Prep List rolls to the next game day once the first day\'s rows have kicked off', async () => {
  const row = (who, kickoff, extra = {}) => ({ ...PREP.CFB.rows[0], athleteId: who, player: who, kickoff, ...extra });
  const prep = { CFB: { day: '2026-10-10', rows: [row('Early Kick', '2026-10-10T13:30:00Z')], next: { day: '2026-10-11', rows: [row('Sunday Guy', '2026-10-11T17:00:00Z')] } } };
  const rolled = await loadApp('#record', {}, { today: { ...TODAY, prep } }).api.views.today({ view: 'today' });
  const sec = rolled.slice(rolled.indexOf('class="kt-sec kt-prep"'), rolled.indexOf('kt-upsets"'));
  assert.match(sec, /<span class="kt-kind">Research for Sunday<\/span>/);
  assert.match(sec, /Sunday Guy/);
  assert.doesNotMatch(sec, /Early Kick/);
  prep.CFB.rows = [row('Still Ahead', '2026-10-10T23:00:00Z')];
  const ahead = await loadApp('#record', {}, { today: { ...TODAY, prep } }).api.views.today({ view: 'today' });
  const sec2 = ahead.slice(ahead.indexOf('class="kt-sec kt-prep"'), ahead.indexOf('kt-upsets"'));
  assert.match(sec2, /Still Ahead/);
  assert.doesNotMatch(sec2, /Sunday Guy/, 'the first game day keeps the list while it has a row to come');
});

test('Today\'s games show live scores and our projected score, with the free scoreboard refresh stamp', async () => {
  const page = await loadApp('#record').api.views.today({ view: 'today' });
  const sec = page.slice(page.indexOf('kt-games"'), page.indexOf('kt-off-card"'));
  assert.match(sec, /<h2 class="kt-head" id="games-h">Other games today<\/h2>/);
  assert.match(sec, /class="proj[^"]*" href="#game\/CFB-2"/, 'other covered games stay visible');
  assert.doesNotMatch(sec, /class="proj[^"]*" href="#game\/NFL-1"/, 'the NFL spotlight is not repeated');
  assert.match(sec, /live-stamp/);
  const live = { ...GAMES[0], state: 'in', status: '2nd 4:12', v2: { away: 23.1, home: 20.4, total: 43.5 }, away: { ...GAMES[0].away, score: 7 }, home: { ...GAMES[0].home, score: 3 } };
  const page2 = await loadApp('#record', {}, { today: { ...TODAY, games: [live, GAMES[1]] } }).api.views.today({ view: 'today' });
  const spot = page2.slice(page2.indexOf('kt-nfl-now"'), page2.indexOf('kt-games"'));
  assert.match(spot, /Live<\/small><b class="num">7<i> – <\/i>3<\/b><span>We had 23–20<\/span>/, 'the spotlight keeps the live score and projected score');
  const nflOnly = await loadApp('#record', {}, { today: { ...TODAY, games: [live] } }).api.views.today({ view: 'today' });
  assert.match(nflOnly, /kt-nfl-now"/);
  assert.doesNotMatch(nflOnly, /kt-games"/, 'an NFL-only day has no duplicate games section');
});

test('Fun tickets and Pulled before kickoff are visible sections when they have plays, and absent when empty', async () => {
  const fun = { ...total, id: 'CFB-2026-W6-fun-longshot', kind: 'parlays', parlayType: 'longshot', legs: ['Leg A over 40.5', 'Leg B over 3.5'], odds: 450, displayTitle: 'Longshot' };
  const gone = { ...total, id: 'CFB-2026-W6-pulled', posted: true, displayTitle: 'Pulled Team at Other under 50.5', status: 'withdrawn', entryNote: 'Pulled over news before its post went out.' };
  const todayOff = { ...total, id: 'CFB-today-off-fd', displayTitle: 'Moved Line Today under 56.5', status: 'expired',
    entryNote: 'Closed to new entries at 11:45 AM ET: total moved 3 against, from 56.5 to 53.5.' };
  const page = await loadApp('#record', {}, { today: { ...TODAY, picks: [...TODAY.picks, fun, gone, todayOff] } }).api.views.today({ view: 'today' });
  assert.match(page, /<h2 class="kt-head" id="fun-h">Fun tickets<\/h2><span class="kt-kind">Smaller stake, apart from best bets<\/span>/);
  assert.match(page, /<h2 class="kt-head" id="pulled-h">Pulled before kickoff · 1<\/h2>[\s\S]*Pulled Team at Other/);
  const at = s => page.indexOf(s);
  assert.ok(at('kt-games"') < at('kt-fun"') && at('kt-fun"') < at('kt-pulled"') && at('kt-pulled"') < at('kt-off-card"'));
  const plain = await loadApp('#record').api.views.today({ view: 'today' });
  assert.ok(!plain.includes('kt-fun"') && !plain.includes('kt-pulled"'));
});

test('an owner community ticket is unmistakably personal and separate from best bets', async () => {
  const personal = { ...total, id: 'community:personal-ticket:sea-den', community: true, personalTicket: true,
    kind: 'parlays', parlayType: 'community', riskUnits: 0.25, odds: 9023, book: 'FanDuel',
    displayTitle: '7-leg boosted Fun Lotto', legs: ['Seattle -2.5', 'AJ Barner anytime touchdown'] };
  const page = await loadApp('#record', {}, { today: { ...TODAY, picks: [...TODAY.picks, personal] } }).api.views.today({ view: 'today' });
  assert.match(page, /Personal fun ticket/);
  assert.doesNotMatch(page, /Personal Fun Lotto · 0\.25u/);
  assert.match(page, /My card · tracked separately from Best Bets/);
  assert.doesNotMatch(page.slice(page.indexOf('Personal fun ticket')), /Hot Plate \(POTD\)/);
});


test('Today results keep personal losses and cash-outs separate from Best Bet units', async () => {
  const official = {...yesterday, result:'loss', units:-1};
  const personal = {...yesterday, id:'personal-loss', community:true, lane:'personal', result:'loss', units:null, accountingUnknown:true};
  const cashout = {...personal, id:'personal-cashout', result:'push', cashout:true, units:0, accountingUnknown:false};
  const page = await loadApp('#record', {}, {today:{...TODAY,picks:[official,personal,cashout]}}).api.views.today({view:'today'});
  assert.match(page, /Friday results/);
  assert.match(page, /Best Bets: 0–1/);
  assert.match(page, /My Card: 0–1<\/b> · 1 cashed out · net unavailable/);
  assert.match(page, /Cashed out · not a sportsbook push/);
  assert.doesNotMatch(page, /Friday went 0-2-1|All posted plays · Best Bets/);
});

test('Today pulled strip shares public delivery eligibility with Record', async () => {
  const withdrawn = { ...total, id: 'CFB-2026-W6-never-posted', status: 'withdrawn',
    displayTitle: 'Never Released under 50.5', entryNote: 'Pulled before posting: hard news.' };
  assert.equal(C.countsPublic(withdrawn), false);
  const hidden = await loadApp('#record', {}, { today: { ...TODAY, picks: [withdrawn] } }).api.views.today({ view: 'today' });
  assert.doesNotMatch(hidden, /kt-pulled"|Never Released|each still counts/);
  for (const delivery of [{ posted: true }, { delivery: { discordAt: '2026-10-10T13:00:00Z' } },
    { delivery: { xAt: '2026-10-10T13:15:00Z' } }]) {
    const released = { ...withdrawn, ...delivery, displayTitle: 'Released then pulled under 50.5' };
    assert.equal(C.countsPublic(released), true);
    const shown = await loadApp('#record', {}, { today: { ...TODAY, picks: [released] } }).api.views.today({ view: 'today' });
    assert.match(shown, /Pulled before kickoff · 1/);
    assert.match(shown, /Released then pulled/);
    assert.match(shown, /each still counts/);
  }
});
