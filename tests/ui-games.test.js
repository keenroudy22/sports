'use strict';
/* The Games bundle (app-games.js): the slate with the college navigator, the game page with "Why my number differs",
   live scores and the team page, rendered through the real shared interface with fixture data. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const gamesSource = fs.readFileSync('site/app-games.js', 'utf8');

const unesc = html => String(html).replace(/&#39;/g, "'");
const loadBrowserApi = () => {
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: C, KRLive: L, KRPersonal: P,
    document: { querySelector: () => null },
    localStorage: { getItem: () => null, setItem: () => {} },
    console, URL, URLSearchParams, Intl, Date, Math, Map, Set, Promise,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox; sandbox.self = sandbox; sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(gamesSource, sandbox, { filename: 'site/app-games.js' });
  return { api: sandbox.module.exports, factory: sandbox.KRGames };
};

const SOON = new Date(Date.now() + 36 * 3600000);
const kickoff = (hourET, dayOffset = 0) => { const d = new Date(SOON); d.setUTCDate(d.getUTCDate() + dayOffset); d.setUTCHours(hourET + 4, 0, 0, 0); return d.toISOString(); };
const team = (id, abbr, name, off, def) => ({ id, abbr, name, color: '#123456', score: null, strength: { offense: off, defense: def, teams: 136 } });
const game = (id, home, away, spread, total, margin, ourTotal, extra = {}) => ({
  id, league: 'CFB', state: 'pre', completed: false, kickoff: kickoff(12), home, away,
  market: { spread, total, book: 'DraftKings', displayBook: 'DraftKings', retrievedAt: new Date(Date.now() - 600000).toISOString(), spreadOpen: spread, totalOpen: total },
  v2: { margin, total: ourTotal, home: 30, away: 30 - margin, winProb: 0.6, sparse: false, model: 'v2.0' },
  gap: { model: margin, book: -spread, difference: Math.round((margin + spread) * 10) / 10 },
  tier: Math.abs(spread) <= 7 ? 'competitive' : Math.abs(spread) < 14 ? 'lean' : Math.abs(spread) < 21 ? 'mismatch' : 'blowout',
  window: 'noon', conference: { home: 'SEC', away: 'Sun Belt' }, ranked: { home: null, away: null },
  bettable: 5, bettableParts: { spread: true, total: true, props: 0, official: false, upset: false }, look: 'Even matchup',
  plainGap: 'Even matchup by my numbers (gap 1) and the book is close (3): sides and totals are live here.',
  garbageTime: Math.abs(spread) >= 21, whyDiffer: null, ...extra,
});

const slate = () => {
  const a = game('CFB-1', team('1', 'BAMA', 'Alabama', 2, 5), team('2', 'USA', 'South Alabama', 90, 110), -28, 55.5, 24, 52,
    { window: 'noon', bettable: 3, tier: 'blowout', garbageTime: true, look: 'Props carry garbage-time risk',
      plainGap: 'Alabama is 24 points better by my numbers and the book has Alabama by 28. Starters may sit early.',
      whyDiffer: { stale: false, kind: 'spread', ours: 24, book: 28, gap: -4, text: 'I have 24, the book has 28. Alabama had a 28-point-or-larger result in its last three games.',
        caution: 'Alabama had a 28-point-or-larger result in its last three games.',
        drivers: [{ text: 'Alabama had a 28-point-or-larger result in its last three games.', direction: -1, weight: 1, flag: 'blowout', numbers: [28] },
          { text: "Alabama's offense ranks 2 of 136; South Alabama's defense ranks 110.", direction: 1, weight: 7.2, numbers: [2, 136, 110] }],
        markets: { spread: { ours: 24, book: 28, gap: -4, drivers: [{ text: "Alabama's offense ranks 2 of 136; South Alabama's defense ranks 110.", direction: 1, weight: 7.2, numbers: [2, 136, 110] }, { text: 'Alabama had a 28-point-or-larger result in its last three games.', direction: -1, weight: 1, flag: 'blowout', numbers: [28] }], caution: 'Alabama had a 28-point-or-larger result in its last three games.' }, total: null } } });
  const b = game('CFB-2', team('3', 'PITT', 'Pitt', 9, 22), team('4', 'GASO', 'Georgia Southern', 60, 70), -4, 53.5, 4.6, 50.5,
    { window: 'afternoon', kickoff: kickoff(15.5), bettable: 8, look: 'Total 53.5 vs my 50.5', conference: { home: 'ACC', away: 'Sun Belt' },
      whyDiffer: { stale: false, kind: 'total', ours: 50.5, book: 53.5, gap: -3, text: 'I have 50.5, the book has 53.5. Pitt\'s defense ranks 22 of 136 in my model.', caution: null,
        drivers: [{ text: "Pitt's defense ranks 22 of 136 in my model.", direction: 1, weight: 3.1, numbers: [22, 136] }, { text: "Pitt's last three games totaled 38, 41, 44.", direction: 1, weight: 2.5, numbers: [38, 41, 44] }],
        markets: { spread: null, total: { ours: 50.5, book: 53.5, gap: -3, caution: null, drivers: [{ text: "Pitt's defense ranks 22 of 136 in my model.", direction: 1, weight: 3.1, numbers: [22, 136] }, { text: "Pitt's last three games totaled 38, 41, 44.", direction: 1, weight: 2.5, numbers: [38, 41, 44] }] } } } });
  const c = game('CFB-3', team('5', 'OSU', 'Ohio State', 1, 2), team('6', 'IOWA', 'Iowa', 40, 12), -10, 44.5, 9, 43,
    { window: 'night', kickoff: kickoff(19.5), bettable: 8, look: 'Dog +10 vs my +9', conference: { home: 'Big Ten', away: 'Big Ten' },
      whyDiffer: { stale: true, text: 'The book line is older than four hours; check a current price.', drivers: [] } });
  const d = game('CFB-4', team('7', 'UK', 'Kentucky', 50, 60), team('8', 'UF', 'Florida', 30, 35), -3, 47.5, 1, 47,
    { window: 'night', kickoff: kickoff(19.5), bettable: 5, look: 'Even matchup', conference: { home: 'SEC', away: 'SEC' } });
  const nfl = { ...game('NFL-1', team('9', 'KC', 'Chiefs', 1, 5), team('10', 'LV', 'Raiders', 30, 28), -9.5, 44.5, 10, 45), league: 'NFL', window: 'afternoon', kickoff: kickoff(16.25, 1), conference: { home: null, away: null }, bettable: 4, tier: 'lean', look: 'Fresh spread and total' };
  for (const g of [a, b, c, d]) g.kickoff = g.kickoff || kickoff(12);
  return [a, b, c, d, nfl];
};

const contextFor = (api, games, overrides = {}) => {
  const base = api.moreContext();
  Object.assign(base.state, { league: 'CFB', games: { sort: 'bettable', all: false, q: '', day: null, status: 'all', upDay: null, nav: { window: 'all', close: false, conf: 'all' } }, watchlist: [], ticket: [] });
  const today = { games, picks: [], freshness: {}, health: [] };
  return api.gamesContext({ get: async path => path === 'app/today.json' ? today : (() => { throw new Error('no ' + path); })(),
    maybe: async () => null, teamDirectory: async () => ({ teams: {}, defense: { season: 2026, rows: {} } }), lineData: async () => ({ lines: [] }),
    withLive: list => ({ games: list, refreshed: null }), liveStamp: () => '', liveFor: () => null, ...overrides });
};

test('the college slate sorts by bettability, shows tiers and keeps NFL in kickoff order with badges only', async () => {
  const { api, factory } = loadBrowserApi();
  const games = slate();
  const views = factory(contextFor(api, games));
  const html = unesc(await views.games({ tab: 'upcoming' }));
  assert.match(html, /<h1/);
  assert.doesNotMatch(html, /Something did not load|is not defined|far from the book line/);
  const order = [...html.matchAll(/href="#game\/(CFB-\d)"/g)].map(m => m[1]).filter((v, i, arr) => arr.indexOf(v) === i);
  assert.deepEqual(order.slice(0, 4), ['CFB-2', 'CFB-3', 'CFB-4', 'CFB-1'], 'bettable first, ties by kickoff, blowout last');
  assert.match(html, /Blowout · gap 28/);
  assert.match(html, /Competitive · gap 4/);
  assert.match(html, /Worth your time/);
  assert.match(html, /Total 53\.5 vs my 50\.5/);
  assert.match(html, /What.s bettable/);
  assert.match(html, /Garbage-time risk/);
  assert.match(html, /Dig deeper ›/);
  assert.match(html, /href="#game\/CFB-2#why"/);
  assert.match(html, /Starters may sit early/);
  assert.match(html, /data-set="gnav:window=noon"/);
  assert.match(html, /data-set="gnav:close=1"/);
  assert.match(html, /data-select="gconf"/);
  assert.match(html, /data-set="gsort:kickoff"/);
  for (const word of ['desk', 'scan', 'automated', 'pipeline', 'calibration', 'model weights']) assert.ok(!new RegExp(`\\b${word}\\b`, 'i').test(html), word);
  const ctx = contextFor(api, games); ctx.state.league = 'NFL'; ctx.state.games.sort = 'bettable';
  const nfl = await factory(ctx).games({ tab: 'upcoming' });
  assert.match(nfl, /Lean · gap 9\.5/);
  assert.doesNotMatch(nfl, /Worth your time/, 'NFL keeps kickoff order and the plain list');
});

test('navigator filters combine: window, close games and conference', async () => {
  const { api, factory } = loadBrowserApi();
  const games = slate();
  const ids = html => [...html.matchAll(/class="proj-link" href="#game\/([A-Z]+-\d)"/g)].map(m => m[1]);
  const ctx = contextFor(api, games);
  ctx.state.games.nav = { window: 'night', close: false, conf: 'all' };
  assert.deepEqual(ids(await factory(ctx).games({ tab: 'upcoming' })).sort(), ['CFB-3', 'CFB-4']);
  ctx.state.games.nav = { window: 'night', close: true, conf: 'all' };
  assert.deepEqual(ids(await factory(ctx).games({ tab: 'upcoming' })), ['CFB-4'], 'close games only keeps competitive tiers');
  ctx.state.games.nav = { window: 'all', close: false, conf: 'SEC' };
  assert.deepEqual(ids(await factory(ctx).games({ tab: 'upcoming' })).sort(), ['CFB-1', 'CFB-4']);
  ctx.state.games.nav = { window: 'noon', close: true, conf: 'SEC' };
  const html = await factory(ctx).games({ tab: 'upcoming' });
  assert.deepEqual(ids(html), []);
  assert.match(html, /No game matches these filters/);
});

test('worth-your-time takes the six highest bettable scores, ties broken by kickoff then id', async () => {
  const { api, factory } = loadBrowserApi();
  const games = slate().filter(g => g.league === 'CFB');
  for (let i = 5; i <= 12; i++) games.push(game(`CFB-${i}`, team(`${i}0`, `T${i}`, `Team ${i}`, 20, 20), team(`${i}1`, `U${i}`, `Other ${i}`, 30, 30), -3, 50, 2, 50, { bettable: 6, kickoff: kickoff(i % 2 ? 12 : 15.5), look: 'Even matchup' }));
  const html = await factory(contextFor(api, games)).games({ tab: 'upcoming' });
  const strip = html.slice(html.indexOf('kt-worth-strip'), html.indexOf('</section>', html.indexOf('kt-worth-strip')));
  const picked = [...strip.matchAll(/href="#game\/(CFB-\d+)"/g)].map(m => m[1]);
  assert.equal(picked.length, 6);
  assert.deepEqual(picked.slice(0, 2), ['CFB-2', 'CFB-3'], 'the two 8s first, earlier kickoff first');
  assert.deepEqual(picked.slice(2), ['CFB-11', 'CFB-5', 'CFB-7', 'CFB-9'], 'then the noon 6s by kickoff, then id (string order, deterministic)');
  const again = await factory(contextFor(api, games.slice().reverse())).games({ tab: 'upcoming' });
  assert.deepEqual([...again.slice(again.indexOf('kt-worth-strip')).matchAll(/href="#game\/(CFB-\d+)"/g)].map(m => m[1]).slice(0, 6), picked, 'input order never changes the pick');
});

test('the game page prints every driver under #why, a note only when a flag fired, and only the staleness line when stale', async () => {
  const { api, factory } = loadBrowserApi();
  const games = slate();
  const detailOf = g => ({ ...g, teams: { home: { injuries: [], form: [] }, away: { injuries: [], form: [] } }, favoriteLines: [], modelReads: [], seasonTrends: [], picks: [], props: { lines: {} } });
  const render = async g => unesc(await factory(contextFor(api, games, { get: async path => path === 'app/today.json' ? { games, picks: [], freshness: {} } : path === `app/games/${g.id}.json` ? detailOf(g) : (() => { throw new Error('no ' + path); })() })).game({ id: g.id }));
  const blowout = await render(games[0]);
  assert.match(blowout, /id="why"/);
  assert.match(blowout, /Why my number differs/);
  assert.match(blowout, /Alabama's offense ranks 2 of 136/);
  assert.match(blowout, /28-point-or-larger/);
  assert.match(blowout, /Blowout · gap 28/);
  assert.match(blowout, /Starters may sit early/);
  assert.match(blowout, /This is my projection against the book's line\. It is research; best bets go through separate price checks\./);
  assert.ok((blowout.match(/kt-why-note/g) || []).length === 1, 'one note because the blowout flag fired');
  assert.doesNotMatch(blowout, /far from the book line|not necessarily a good price/);
  const total = await render(games[1]);
  assert.match(total, /Pitt's last three games totaled 38, 41, 44/);
  assert.doesNotMatch(total, /kt-why-note/, 'no flag, no note');
  const stale = await render(games[2]);
  assert.match(stale, /older than four hours/);
  assert.doesNotMatch(stale, /ranks \d+ of 136 in my model/, 'nothing but the staleness line');
  const even = await render(games[3]);
  assert.doesNotMatch(even, /id="why"/, 'under three points: no section at all');
  for (const html of [blowout, total, stale]) for (const word of ['desk', 'scan', 'automated', 'pipeline', 'calibration']) assert.ok(!new RegExp(`\\b${word}\\b`, 'i').test(html), word);
});

test('a game link may carry a #why anchor and the record a calendar address', () => {
  const { model: M } = require('../site/app.js');
  assert.deepEqual(M.resolve('#game/CFB-2#why'), { view: 'game', id: 'CFB-2', anchor: 'why' });
  assert.deepEqual(M.resolve('#game/CFB-2'), { view: 'game', id: 'CFB-2', anchor: null });
  assert.equal(M.resolve('#record/calendar').anchor, 'calendar');
  assert.equal(M.resolve('#record/calendar').tab, 'official');
  assert.equal(M.canonical(M.resolve('#record/calendar')), null);
});

test('live scores and the team page render from the Games bundle', async () => {
  const { api, factory } = loadBrowserApi();
  const games = slate();
  const views = factory(contextFor(api, games, { maybe: async path => path === 'app/teams/CFB/1.json' ? { id: '1', name: 'Alabama', abbr: 'BAMA', games: [], defense: [] } : path === 'app/players/CFB.json' ? { season: 2026, players: [] } : null }));
  const live = await views.games({ tab: 'live' });
  assert.match(live, /<h1/);
  assert.doesNotMatch(live, /is not defined/);
  const teamPage = await views.team({ league: 'CFB', id: '1' });
  assert.match(teamPage, /<h1>Alabama<\/h1>/);
  assert.match(teamPage, /Blowout · gap 28/, 'the team page cards carry the same badge');
});
