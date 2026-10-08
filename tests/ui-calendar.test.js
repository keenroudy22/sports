'use strict';
/* The results calendar (owner, Oct 7, item 27): Eastern kickoff days, three ledgers that never mix, month totals that
   equal the day cells, best and worst days, filters, today, open rings, tap-to-open slips, and no colour-only meaning. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const C = require('../site/core.js');
const L = require('../site/live.js');
const P = require('../site/personal.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');

/* Freeze the clock on Oct 7, 2026 (afternoon Eastern) so "today", the current month and the disabled next-month arrow
   do not depend on when the suite runs. */
const FIXED_NOW = Date.parse('2026-10-07T18:00:00Z');
class FixedDate extends Date {
  constructor(...a) { super(...(a.length ? a : [FIXED_NOW])); }
  static now() { return FIXED_NOW; }
}

const load = () => {
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: C, KRLive: L, KRPersonal: P,
    document: { querySelector: () => null },
    localStorage: { getItem: () => null, setItem: () => {} },
    console, URL, URLSearchParams, Intl, Date: FixedDate, Math, Map, Set, Promise,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox; sandbox.self = sandbox; sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  vm.runInNewContext(moreSource, sandbox, { filename: 'site/app-more.js' });
  return { api: sandbox.module.exports, factory: sandbox.KRMore };
};

const picks = [
  { id: 'a', league: 'NFL', kind: 'props', odds: -110, result: 'win', kickoff: '2026-10-04T17:00:00Z', settledAt: '2026-10-04T21:00:00Z', title: 'A Player OVER 3.5 receptions', displayTitle: 'A Player OVER 3.5 receptions', athleteId: '1', market: 'rec', direction: 'over', line: 3.5, posted: true, card: 'data/cards/a.png', book: 'FanDuel' },
  { id: 'b', league: 'NFL', kind: 'gamePicks', odds: 120, result: 'loss', kickoff: '2026-10-04T20:00:00Z', settledAt: '2026-10-05T00:00:00Z', title: 'Bears +3.5', displayTitle: 'Bears +3.5', marketType: 'spread', line: 3.5, book: 'DraftKings' },
  /* 00:30Z on Oct 5 is 8:30 PM Eastern on Oct 4: the cell never moves. */
  { id: 'c', league: 'CFB', kind: 'props', odds: -110, result: 'push', kickoff: '2026-10-05T00:30:00Z', settledAt: '2026-10-05T04:00:00Z', title: 'C Player OVER 50.5 rushing yards', displayTitle: 'C Player OVER 50.5 rushing yards', athleteId: '2', market: 'rushYds', direction: 'over', line: 50.5, book: 'DraftKings' },
  { id: 'd', league: 'NFL', kind: 'props', odds: -115, priceAssumed: true, result: 'win', kickoff: '2026-09-06T17:00:00Z', settledAt: '2026-09-06T21:00:00Z', title: 'Week 1 leg', displayTitle: 'Week 1 leg' },
  { id: 'e', league: 'NFL', kind: 'parlays', parlayType: 'longshot', odds: 500, riskUnits: 0.25, result: 'loss', kickoff: '2026-10-04T17:00:00Z', settledAt: '2026-10-05T00:00:00Z', legs: ['A', 'B'], title: 'Fun ticket', displayTitle: 'Fun ticket' },
  { id: 'f', league: 'NFL', kind: 'parlays', parlayType: 'ladder', odds: -150, result: 'win', kickoff: '2026-10-02T23:00:00Z', publishedAt: '2026-10-02T15:00:00Z', settledAt: '2026-10-03T03:00:00Z', legs: ['L1', 'L2'], title: 'Step 2', ladder: { stake: 75, payout: 117, run: 1, step: 2, banked: 19, bankedAfter: 42, nextStake: 94 } },
  { id: 'g', league: 'CFB', kind: 'parlays', parlayType: 'ladder', odds: -150, result: 'loss', kickoff: '2026-10-04T17:00:00Z', publishedAt: '2026-10-04T15:00:00Z', settledAt: '2026-10-04T21:00:00Z', legs: ['L3', 'L4'], title: 'Step 1', ladder: { stake: 50, run: 2, step: 1, banked: 0 } },
  { id: 'h', league: 'NFL', kind: 'props', odds: -110, kickoff: '2026-10-11T17:00:00Z', title: 'Open play', displayTitle: 'Open play OVER 1.5 receptions', athleteId: '3', market: 'rec', direction: 'over', line: 1.5, book: 'FanDuel' },
  { id: 'i', league: 'NFL', kind: 'props', odds: null, historicalImport: true, result: 'win', kickoff: '2026-09-06T17:00:00Z', title: 'Hand-posted leg' },
  /* A voided play (a leg the book's injury rule removed): outside W-L-P and the units, like the Record headline. */
  { id: 'j', league: 'NFL', kind: 'props', odds: -110, result: 'void', kickoff: '2026-09-13T17:00:00Z', settledAt: '2026-09-13T21:00:00Z', title: 'Voided TD leg', displayTitle: 'Voided TD leg' },
];

const views = (overrides = {}) => {
  const { api, factory } = load();
  const base = api.moreContext();
  Object.assign(base.state, { league: 'ALL', record: { season: 'current', phase: 'current', q: '', cal: { month: '2026-10', league: 'ALL', ledger: 'best', day: null, ...overrides } }, watchlist: [], ticket: [] });
  const today = { games: [], picks: [], freshness: {}, health: [] };
  const ctx = api.moreContext({ get: async () => today, maybe: async () => null, allPicks: async () => picks, teamDirectory: async () => ({ teams: {}, defense: {} }), lineData: async () => ({ lines: [] }) });
  return factory(ctx);
};
const near = (a, b) => Math.abs(a - b) < 1e-9;

test('days are keyed by the Eastern kickoff date and month totals equal the sum of the day cells', () => {
  const cal = views().calendarModel;
  const m = cal.month(picks, '2026-10', 'best', 'ALL');
  assert.deepEqual([...m.days.keys()], ['2026-10-04', '2026-10-11']);
  const oct4 = m.days.get('2026-10-04');
  assert.deepEqual([oct4.wins, oct4.losses, oct4.pushes, oct4.plays, oct4.open], [1, 1, 1, 3, 0], 'the 00:30Z push lands on Oct 4 Eastern');
  assert.ok(near(oct4.net, C.unitsFor(picks[0]) + C.unitsFor(picks[1]) + 0), 'units are core.js unitsFor, summed');
  assert.ok(near(m.totals.net, [...m.days.values()].reduce((s, d) => s + d.net, 0)));
  assert.deepEqual([m.totals.wins, m.totals.losses, m.totals.pushes, m.totals.open], [1, 1, 1, 1]);
  assert.equal(m.days.get('2026-10-11').open, 1);
  assert.equal(m.days.get('2026-10-11').plays, 0);
  assert.equal(m.totals.priced, 3, 'all three graded October plays carry a recorded price');
  assert.ok(near(m.totals.perPlay, m.totals.net / m.totals.priced));
  assert.equal(m.totals.best, null, 'a losing month has no best day');
  assert.equal(m.totals.worst.day, '2026-10-04');
  assert.ok(near(m.totals.worst.net, oct4.net));
});

test('the three ledgers never mix and the Climb is in dollars', () => {
  const cal = views().calendarModel;
  const best = cal.month(picks, '2026-10', 'best', 'ALL');
  assert.ok(![...best.days.values()].some(d => d.rows.some(p => C.isParlay(p))), 'no ticket or rung in the best-bet ledger');
  const fun = cal.month(picks, '2026-10', 'fun', 'ALL');
  assert.deepEqual([...fun.days.keys()], ['2026-10-04']);
  assert.ok(near(fun.days.get('2026-10-04').net, -0.25));
  assert.equal(fun.totals.losses, 1);
  const climb = cal.month(picks, '2026-10', 'climb', 'ALL');
  assert.deepEqual([...climb.days.keys()], ['2026-10-02', '2026-10-04']);
  assert.equal(climb.days.get('2026-10-02').net, 42, 'a win returns the payout; net is payout minus stake');
  assert.equal(climb.days.get('2026-10-04').net, -50, 'a loss returns nothing');
  assert.equal(climb.totals.net, -8);
  assert.deepEqual([climb.totals.best.day, climb.totals.best.net], ['2026-10-02', 42]);
  assert.deepEqual([climb.totals.worst.day, climb.totals.worst.net], ['2026-10-04', -50]);
  const sept = cal.month(picks, '2026-09', 'best', 'ALL');
  assert.deepEqual([sept.totals.wins, sept.totals.net, sept.totals.assumed], [1, 0, 1], 'Week 1 counts in W-L, not in units; the unpriced import is excluded');
  assert.deepEqual([sept.totals.pushes, sept.totals.voids, sept.totals.plays], [0, 1, 2], 'the void is counted apart from pushes');
  assert.equal(sept.totals.perPlay, null, 'no priced play, no per-play figure: the assumed-price play is not a denominator');
  const sept13 = sept.days.get('2026-09-13');
  assert.deepEqual([sept13.wins, sept13.losses, sept13.pushes, sept13.voids], [0, 0, 0, 1]);
  const cfb = cal.month(picks, '2026-10', 'best', 'CFB');
  assert.deepEqual([cfb.totals.wins, cfb.totals.losses, cfb.totals.pushes, cfb.totals.net], [0, 0, 1, 0]);
  assert.deepEqual([cal.grid('2026-10').offset, cal.grid('2026-10').days], [3, 31], 'October 1, 2026 is a Thursday: three Monday-first pads');
  assert.equal(cal.shift('2026-01', -1), '2025-12');
  assert.equal(cal.label('2026-10'), 'October 2026');
});

test('the rendered calendar has a header, filters, totals, ink-on-fill cells with numbers, today and open rings', async () => {
  const html = await views().record({ tab: 'official' });
  assert.match(html, /<section class="cal" id="calendar"/);
  assert.match(html, /<h2 id="cal-h">October 2026<\/h2>/);
  assert.match(html, /data-set="rcal:month=2026-09" aria-label="Previous month"/);
  assert.match(html, /data-set="rcal:month=2026-11" aria-label="Next month" disabled/, 'no month beyond the current one');
  assert.match(html, /data-set="rcal:league=NFL" aria-pressed="false"/);
  assert.match(html, /data-set="rcal:league=ALL" aria-pressed="true"/);
  assert.match(html, /data-set="rcal:ledger=fun" aria-pressed="false"/);
  assert.match(html, /data-set="rcal:ledger=best" aria-pressed="true"/);
  assert.match(html, /<button type="button" class="cal-day neg" data-set="rcal:day=2026-10-04" aria-pressed="false" aria-label="Oct 4: 1-1-1, −0\.09u"><span class="d">4<\/span><b class="n num">−0\.09<\/b><small>1-1-1<\/small><\/button>/, 'a loss under a tenth shows two decimals, never −0.0');
  assert.match(html, /<small>Per play<\/small><b class="num">−0\.03u<\/b><span>net ÷ priced plays<\/span>/);
  assert.ok(html.indexOf('<section class="cal"') < html.indexOf('class="kpis'), 'the calendar sits at the top of the Record, above the headline strip');
  assert.match(moreSource, /\.cal \{[^}]*scroll-margin-top: 64px/, 'landing on #record/calendar clears the sticky header');
  assert.match(html, /class="cal-day none open" data-set="rcal:day=2026-10-11"[^>]*><span class="d">11<\/span><small>open<\/small>/);
  assert.match(html, /class="cal-day none today"><span class="d">7<\/span>/, 'today (Oct 7) carries the outline');
  for (const cell of html.match(/<button type="button" class="cal-day (pos|neg|zero)[^]*?<\/button>/g) || []) assert.match(cell, /<b class="n num">[−+]?\d/, 'every filled cell shows its number');
  assert.match(html, /<small>Record<\/small><b class="num">1–1–1<\/b>/);
  assert.match(html, /<small>Worst day<\/small><b class="num red">−0\.09u<\/b><span>Oct 4<\/span>/);
  assert.match(html, /<small>Best day<\/small><b class="num green">–<\/b>/);
  assert.match(html, /Green with a plus is a winning day, red with a minus a losing day/);
  assert.doesNotMatch(html, /Week 1 at an assumed/, 'October has no assumed-price plays');
  assert.doesNotMatch(html, /far from the book line/);
  const september = await views({ month: '2026-09' }).record({ tab: 'official' });
  assert.match(september, /Week 1 at an assumed −115/);
  assert.match(september, /One void play this month: not counted in W–L or units/);
  assert.match(september, /aria-label="Sep 13: 0-0, 0\.00u"/, 'the void day shows no P');
  assert.match(september, /<small>Per play<\/small><b class="num">–<\/b>/, 'no priced September play in the fixture, so no per-play figure');
  const future = await views({ month: '2027-03' }).record({ tab: 'official' });
  assert.match(future, /<h2 id="cal-h">October 2026<\/h2>/, 'a future month falls back to the current one');
});

test('tapping a day opens its slips with the card link; tapping again closes it; the Climb shows its dollar rows', async () => {
  const open = await views({ day: '2026-10-04' }).record({ tab: 'official' });
  assert.match(open, /data-set="rcal:day=2026-10-04" aria-pressed="true"/);
  assert.match(open, /<div class="cal-slips" id="cal-day">/);
  assert.match(open, /A Player/);
  assert.match(open, /<a class="cal-card" href="data\/cards\/a\.png" target="_blank" rel="noopener">See the card ↗<\/a>/);
  assert.equal((open.match(/See the card ↗/g) || []).length, 1, 'only the play with a card file gets the link');
  assert.match(open, /kt-stamp hit/);
  assert.match(open, /kt-stamp miss/);
  const closed = await views().record({ tab: 'official' });
  assert.doesNotMatch(closed, /cal-slips/);
  const climb = await views({ ledger: 'climb', day: '2026-10-02' }).record({ tab: 'official' });
  assert.match(climb, /<small>Steps<\/small><b class="num">1–1<\/b>/);
  assert.match(climb, /Step 2/);
  assert.match(climb, /\$75 → \$117/);
  assert.match(climb, /class="cal-day pos" data-set="rcal:day=2026-10-02" aria-pressed="true" aria-label="Oct 2: 1-0, \+\$42"/);
  const fun = await views({ ledger: 'fun' }).record({ tab: 'official' });
  assert.match(fun, /class="cal-day neg" data-set="rcal:day=2026-10-04" aria-pressed="false" aria-label="Oct 4: 0-1, −0\.25u"/);
  assert.match(fun, /Fun tickets keep their own 0\.25u ledger/);
});

test('the header sport filters the calendar and hides the league chips', async () => {
  const { api, factory } = load();
  const base = api.moreContext();
  Object.assign(base.state, { league: 'CFB', record: { season: 'current', phase: 'current', q: '', cal: { month: '2026-10', league: 'ALL', ledger: 'best', day: null } }, watchlist: [], ticket: [] });
  const ctx = api.moreContext({ get: async () => ({ games: [], picks: [], freshness: {}, health: [] }), maybe: async () => null, allPicks: async () => picks, teamDirectory: async () => ({ teams: {}, defense: {} }), lineData: async () => ({ lines: [] }) });
  const html = await factory(ctx).record({ tab: 'official' });
  assert.doesNotMatch(html, /data-set="rcal:league=/);
  assert.match(html, /College football only · pick All sports above/);
  assert.match(html, /aria-label="Oct 4: 0-0-1, 0\.00u"/, 'only the CFB push counts');
});

test('the season units line highlights the month and the setter toggles a tapped day', async () => {
  const html = await views().record({ tab: 'official' });
  assert.match(html, /<rect x="[\d.]+" y="0" width="[\d.]+" height="\d+" fill="rgba\(242, 247, 244, \.08\)" rx="6"><title>October 2026<\/title><\/rect>/);
  assert.match(source, /rcal: v => \{ const \[k, x\] = v\.split\('='\); state\.record\.cal\[k\] = k === 'day' && state\.record\.cal\.day === x \? null : x;/);
  assert.match(source, /case 'record': return \{ view: 'record', tab: \[.*\]\.includes\(a\) \? a : 'official', anchor: a === 'calendar' \? 'calendar' : null \}/);
});
