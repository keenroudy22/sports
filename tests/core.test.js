'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');

const KEYS = ['recYds', 'rec', 'recLong', 'snapPct'];
// [eventId, date, season, week, seasonType, team, opp, home, ...stats]
const row = (date, opp, home, recYds, rec, extra = {}) =>
  ['e' + date, date, Number(date.slice(0, 4)), 1, 2, '1', opp, home, recYds, rec, extra.recLong ?? null, extra.snapPct ?? null];

test('text helpers escape markup and format numbers without claiming precision', () => {
  assert.equal(C.esc('<b>"x" & y</b>'), '&lt;b&gt;&quot;x&quot; &amp; y&lt;/b&gt;');
  assert.equal(C.odds(150), '+150');
  assert.equal(C.odds(-110), '-110');
  assert.equal(C.odds(null), C.DASH);
  assert.equal(C.signed(2.25), '+2.3');
  assert.equal(C.signed(-3), '-3.0');
  assert.equal(C.signed(0), '0.0');
  assert.equal(C.spreadText('ATL', 2.5), 'ATL +2.5');
  assert.equal(C.spreadText('ATL', -3), 'ATL -3');
  assert.equal(C.spreadText('ATL', 0), 'ATL PK');
  assert.equal(C.modelSpread('ATL', 'CAR', 4.3), 'ATL -4.3');
  assert.equal(C.modelSpread('ATL', 'CAR', -2), 'CAR -2.0');
  assert.equal(C.modelSpread('ATL', 'CAR', 0.01), 'Even');
  assert.equal(C.ago(null), 'time not recorded', 'a missing time is not January 1970');
  assert.equal(C.when(null), '');
});

test('leans name the team and the total direction the model prefers', () => {
  const game = { home: { abbr: 'ATL' }, away: { abbr: 'CAR' }, lean: { spread: 6.8, side: 'home', total: -2.3 } };
  assert.deepEqual(C.leanText(game), { side: { team: 'ATL', points: 6.8, chance: null }, total: { direction: 'Under', points: 2.3, chance: null } });
  assert.equal(C.leanTone(0.58, false), 'lean-strong');
  assert.equal(C.leanTone(0.58, true), 'lean-mild', 'a thin sample never shows green');
  assert.equal(C.leanTone(0.55, false), 'lean-mild');
  assert.equal(C.leanTone(0.52, false), '');
  assert.equal(C.leanTone(null, false), '');
  assert.deepEqual(C.leanText({ ...game, lean: { spread: 1, side: 'home', total: 0.5 } }, 2), {});
  assert.equal(C.leanText({ home: {}, away: {} }), null);
});

test('windows count back from the newest game and report their true sample', () => {
  const rows = [row('2025-09-07', '2', 1, 50, 4), row('2025-09-14', '3', 0, 80, 6), row('2026-09-10', '4', 1, 120, 9)];
  const w = C.windows(rows, KEYS, 'recYds', [2, 5]);
  assert.equal(w.last2.n, 2);
  assert.equal(w.last2.avg, 100);
  assert.equal(w.last5.n, 3);
  assert.equal(w.season.n, 1, 'the season is the newest game’s season');
  assert.equal(w.season.avg, 120);
});

test('a listed player without a counting stat had zero, but longest and snaps stay unknown', () => {
  const r = row('2026-09-10', '4', 1, null, null);
  assert.equal(C.cell(r, KEYS, 'recYds'), 0);
  assert.equal(C.cell(r, KEYS, 'recLong'), null);
  assert.equal(C.cell(r, KEYS, 'snapPct'), null);
  assert.equal(C.cell(r, KEYS, 'notAKey'), null);
});

test('splits separate home, away and neutral and list head-to-head meetings', () => {
  const rows = [row('2025-09-07', '2', 1, 50, 4), row('2025-09-14', '2', 0, 80, 6), row('2026-01-04', '3', -1, 20, 1)];
  const s = C.splits(rows, KEYS, 'recYds', '2');
  assert.equal(s.home.avg, 50);
  assert.equal(s.away.avg, 80);
  assert.equal(s.neutral.avg, 20);
  assert.equal(s.vs.summary.n, 2);
  assert.deepEqual(s.vs.games.map(g => g.value), [50, 80]);
  assert.deepEqual(C.hits([50, 80, 20, 60.5], 60.5), { over: 1, under: 2, push: 1, n: 4 });
});

test('a market’s words map to the stat behind it, and a row that names its stat wins', () => {
  assert.equal(C.marketKey({ market: 'receiving yards' }), 'recYds');
  assert.equal(C.marketKey({ market: 'rushing attempts' }), 'car');
  assert.equal(C.marketKey({ market: 'pass attempts' }), 'att');
  assert.equal(C.marketKey({ title: 'Terrance Ferguson under 32.5 receiving yards' }), 'recYds');
  assert.equal(C.marketKey({ market: 'longest reception' }), null);
  assert.equal(C.marketKey({ market: 'receiving yards', stat: 'rec' }), 'rec');
  assert.equal(C.marketKey(null), null);
});

test('a role ranks a player among teammates at his position by the volume behind the market', () => {
  const players = [{ id: '1', pos: 'TE', targets: [5.1, 2, 8] }, { id: '2', pos: 'TE', targets: [2.3, 0, 5] },
    { id: '3', pos: 'WR', targets: [9, 5, 13] }, { id: '4', pos: 'TE' }];
  assert.deepEqual(C.roleOf(players, '2', 'TE', 'recYds'), { rank: 2, of: 2, stat: 'targets', volume: 2.3 });
  assert.equal(C.roleOf(players, '3', 'TE', 'recYds'), null, 'a receiver is not ranked among tight ends');
  assert.equal(C.roleOf(players, '1', 'TE', 'recLong'), null, 'no volume stat stands behind a longest-play line');
  assert.equal(C.POS_GROUP.FB, 'RB');
});

test('defense ranks put the stingiest first, share ranks on ties and ignore missing rows', () => {
  const rows = { A: { g: 2, WR: { recYds: 150 } }, B: { g: 2, WR: { recYds: 100 } }, C: { g: 2, WR: { recYds: 150 } }, D: { g: 2, TE: { recYds: 40 } } };
  const ranked = C.rankDefenses(rows, 'WR', 'recYds');
  assert.deepEqual(ranked.map(r => [r.team, r.rank]), [['B', 1], ['A', 2], ['C', 2]]);
  assert.deepEqual(C.rankOf(rows, 'C', 'WR', 'recYds'), { rank: 2, of: 3, value: 150 });
  assert.equal(C.rankOf(rows, 'D', 'WR', 'recYds'), null);
  assert.equal(C.rankTone(30, 32), 'soft');
  assert.equal(C.rankTone(3, 32), 'tough');
  assert.equal(C.rankTone(16, 32), 'neutral');
});

const now = Date.parse('2026-09-19T12:00:00Z');
const leg = (id, odds, extra = {}) => ({ id, odds, book: 'DraftKings', gameId: 'NFL-' + id, state: 'open', kickoff: '2026-09-20T17:00:00Z', title: 'Leg ' + id, ...extra });

test('an illustrative parlay multiplies separate-game prices at one book', () => {
  const t = C.summarizeTicket([leg('1', -110), leg('2', 150)], 1, 'units', 10, now);
  assert.equal(t.available, true);
  assert.ok(Math.abs(t.decimal - (1 + 100 / 110) * 2.5) < 1e-9);
  assert.equal(t.odds, 377);
  assert.ok(Math.abs(t.dollars.profit - 37.73) < 0.01);
  assert.equal(C.american(2), 100);
  assert.equal(C.american(1.5), -200);
});

test('a ticket refuses what the sportsbook would price differently or not at all', () => {
  const reason = rows => C.summarizeTicket(rows, 1, 'units', 10, now).reason;
  assert.match(reason([leg('1', -110)]), /at least two/);
  assert.match(reason([leg('1', -110), leg('2', 150, { book: 'FanDuel' })]), /Mixed sportsbooks/);
  assert.match(reason([leg('1', -110), leg('2', 150, { gameId: 'NFL-1' })]), /Same-game/);
  assert.match(reason([leg('1', -110), leg('2', 150, { kickoff: '2026-09-18T17:00:00Z' })]), /current, priced/);
  assert.match(reason([leg('1', -110), leg('2', null)]), /current, priced/);
  assert.match(C.summarizeTicket([leg('1', -110), leg('2', 150)], 0, 'units', 10, now).reason, /positive stake/);
  assert.match(C.ticketText([leg('1', -110)]), /not an official ticket/);
});

test('the record counts priced picks only and withholds ROI below ten', () => {
  const picks = [
    { result: 'win', odds: 150 }, { result: 'loss', odds: -110 }, { result: 'push', odds: -110 },
    { result: 'win', odds: null }, { result: 'void', odds: -110 }, { result: null, odds: -110 }];
  const r = C.recordOf(picks);
  assert.equal(r.wins, 2);
  assert.equal(r.losses, 1);
  assert.equal(r.priced, 3, 'an unpriced win and a void never enter returns');
  assert.deepEqual([r.pricedWins, r.pricedLosses, r.unpriced], [1, 1, 1]);
  assert.ok(Math.abs(r.units - 0.5) < 1e-9);
  assert.equal(r.roi, null);
  assert.equal(r.pending, 1);
  const ten = Array.from({ length: 10 }, (_, i) => ({ result: i < 6 ? 'win' : 'loss', odds: 100 }));
  assert.equal(C.recordOf(ten).roi, 20);
});

test('the Week 1 import is listed apart and kept out of the record, its units and its ROI', () => {
  const fs = require('node:fs');
  const report = JSON.parse(fs.readFileSync('research/2026-09-14-NFL-week-1-import.json', 'utf8'));
  const five = new Set(['w1-loveland-rec', 'w1-mayfield-pass', 'w1-otton-rec', 'w1-pollard-carries', 'w1-bateman-rec']);
  /* build_site stamps the report's historicalImport flag on each of its picks, as the site sees them */
  const picks = ['props', 'riskyProps', 'gamePicks', 'parlays'].flatMap(k => report[k] || []).map(p => ({ ...p, historicalImport: report.historicalImport }));
  const all = C.recordOf(picks), favorites = C.recordOf(picks.filter(p => five.has(p.id)));
  assert.equal(picks.length, 26);
  assert.ok(picks.every(C.isUnpricedImport));
  assert.deepEqual([all.wins, all.losses, all.priced, all.units], [0, 0, 0, null], 'no price was recorded, so nothing is totalled');
  assert.deepEqual([all.imported.wins, all.imported.losses, all.imported.voids], [14, 11, 1], 'the results are still shown apart');
  assert.deepEqual([favorites.imported.wins, favorites.imported.losses], [1, 4]);
  const mixed = C.recordOf([...picks, { result: 'win', odds: -110 }, { result: 'loss', odds: -110 }]);
  assert.deepEqual([mixed.wins, mixed.losses, mixed.priced, mixed.unpriced], [1, 1, 2, 0], 'the record and its units describe the same picks');
  assert.equal(C.recordOf([{ result: 'win', odds: -110 }]).imported, null);
});

test('a pick is open only until its quote expires, its entries close or its game starts', () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  const pick = { status: 'active', expiresAt: '2026-09-20T15:30:00Z', kickoff: '2026-09-20T17:00:00Z' };
  assert.equal(C.isOpen(pick, now), true);
  assert.equal(C.isOpen({ ...pick, expiresAt: '2026-09-20T11:30:00Z' }, now), false);
  assert.equal(C.isOpen({ ...pick, kickoff: '2026-09-20T11:00:00Z' }, now), false);
  assert.equal(C.isOpen({ ...pick, status: 'expired' }, now), false);
  assert.equal(C.isOpen({ ...pick, result: 'win' }, now), false);
});

test('a pick says where it stands in words, and red is only for a loss', () => {
  const now = Date.parse('2026-09-20T12:00:00Z');
  const pick = { status: 'active', expiresAt: '2026-09-20T15:30:00Z', kickoff: '2026-09-20T17:00:00Z' };
  const word = p => C.pickState(p, now).word;
  assert.equal(word(pick), 'Open');
  assert.equal(word({ ...pick, entryNote: 'moved 2 against' }), 'Line moved');
  assert.equal(word({ ...pick, expiresAt: '2026-09-20T11:00:00Z' }), 'Price expired');
  assert.equal(word({ ...pick, kickoff: '2026-09-20T11:00:00Z' }), 'In play');
  assert.deepEqual(C.pickState({ ...pick, result: 'win' }, now), { word: 'Won', tone: 'win' });
  assert.deepEqual(C.pickState({ ...pick, result: 'loss' }, now), { word: 'Lost', tone: 'loss' });
  assert.equal(C.pickState({ ...pick, entryNote: 'x' }, now).tone, 'closed', 'a closed pick is grey, not red');
  assert.equal(C.isLongshot({ kind: 'riskyProps' }), true);
  assert.equal(C.isLongshot({ kind: 'parlays', parlayType: 'longshot' }), true);
  assert.equal(C.isLongshot({ kind: 'props' }), false);
});

test('a board line leads with a plain word and backs it with its numbers', () => {
  assert.deepEqual(C.gradeOf({ tier: 'strong', chance: 0.61, push: 0, needs: 0.524, thin: false }),
    { tier: 'strong', word: 'Good value', detail: '61% our chance · 52% to break even' });
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.7, push: 0.03, needs: 0.5, thin: true }).detail, '70% our chance, 3% push · 50% to break even · few games so far');
  assert.deepEqual(C.gradeOf(null), { tier: 'none', word: 'No model read', detail: '' });
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.6, push: 0, needs: 0.524, calibrated: false }).detail, '60% our chance · 52% to break even · raw number');
  assert.equal(C.gradeOf({ tier: 'lean', chance: 0.62, push: 0, needs: null, calibrated: false }).detail, '62% our chance · no price yet · raw number');
  const lines = [{ id: 'a', grade: { tier: 'pass', edge: -2 } }, { id: 'b' }, { id: 'c', grade: { tier: 'strong', edge: 6 } },
    { id: 'd', grade: { tier: 'strong', edge: 9 } }, { id: 'e', grade: { tier: 'lean', edge: 3 } }];
  assert.deepEqual(lines.sort(C.byGrade).map(l => l.id), ['d', 'c', 'e', 'a', 'b']);
  const leans = [{ id: 'thin', grade: { tier: 'lean', edge: 30, thin: true } }, { id: 'solid', grade: { tier: 'lean', edge: 3 } }];
  assert.deepEqual(leans.sort(C.byGrade).map(l => l.id), ['solid', 'thin'], 'a solid sample outranks a bigger thin one');
  assert.equal(C.gradeOf(null, 'FBS vs FCS: v2 is not reliable here').detail, 'FBS vs FCS: v2 is not reliable here');
});

test('pick types match the old results page', () => {
  assert.equal(C.category({ kind: 'gamePicks', marketType: 'total' }), 'Totals');
  assert.equal(C.category({ kind: 'gamePicks', marketType: 'spread' }), 'Spreads');
  assert.equal(C.category({ kind: 'props' }), 'Straights');
  assert.equal(C.category({ kind: 'riskyProps' }), 'Risky lines');
  assert.equal(C.category({ kind: 'parlays', parlayType: 'longshot' }), 'Longshots');
  assert.equal(C.category({ kind: 'parlays' }), 'Parlays');
});

test('old links land on the matching new pages', () => {
  const cases = {
    '': { view: 'today' }, '#sports': { view: 'today' }, '#home': { view: 'today' },
    '#record': { view: 'record' }, '#scores': { view: 'games' }, '#props': { view: 'board' }, '#parlays': { view: 'ticket' },
    '#players': { view: 'stats' }, '#research': { view: 'research' }, '#game/NFL-401872932': { view: 'game', id: 'NFL-401872932' },
    '#player/NFL/4430878': { view: 'player', league: 'NFL', id: '4430878' }, '#player/cfb/5': { view: 'player', league: 'CFB', id: '5' },
    '#sport/MLB': { view: 'scores', league: 'MLB' }, '#stats/defense': { view: 'stats', tab: 'defense' },
    '#team/CFB/2390': { view: 'team', league: 'CFB', id: '2390' }, '#nonsense': { view: 'today' },
    '#pick/CFB-2026-W3-duke-minus-10-vs-stan-dk': { view: 'today', pick: 'CFB-2026-W3-duke-minus-10-vs-stan-dk' },
    '#pick': { view: 'today' },
  };
  for (const [hash, expected] of Object.entries(cases)) assert.deepEqual(C.parseRoute(hash), expected, hash);
  assert.equal(C.shardOf('4430878', 32), 4430878 % 32);
});

test('parlays stay out of the straight-pick units and carry their own stake', () => {
  const picks = [
    { kind: 'gamePicks', odds: -110, result: 'win' },
    { kind: 'gamePicks', odds: -110, result: 'loss' },
    { kind: 'parlays', parlayType: 'longshot', odds: 360, result: 'win', riskUnits: 0.25 },
  ];
  const r = C.recordOf(picks, 2);
  assert.deepEqual([r.wins, r.losses], [1, 1], 'the parlay win is not in the straight record');
  assert.ok(Math.abs(r.units + 0.0909) < 0.001, 'units come from the two straight picks alone');
  assert.equal(r.parlays.staked, 0.25);
  assert.ok(Math.abs(r.parlays.units - 0.9) < 1e-9, '+360 on a quarter unit returns 0.9u');
  assert.ok(Math.abs(C.summaryOf(picks, 2).units - 0.809) < 0.001, 'summaryOf counts everything given to it');
  assert.equal(C.stakeOf({}), 1, 'a pick with no recorded stake is one unit');
});

test('a priced line on a thin sample says too early, not no value', () => {
  const thin = C.gradeOf({ tier: 'pass', chance: 0.81, needs: 0.44, edge: 37, thin: true, calibrated: false });
  assert.equal(thin.word, 'Too early to tell');
  const flat = C.gradeOf({ tier: 'pass', chance: 0.5, needs: 0.52, edge: -2, thin: true });
  assert.equal(flat.word, 'No value');
  const solid = C.gradeOf({ tier: 'lean', chance: 0.62, needs: 0.52, edge: 10, thin: false });
  assert.equal(solid.word, 'Some value');
});

test('a paused market never reads as value, and the site shows the calibrated verdict over the raw tier', () => {
  const paused = C.gradeOf({ tier: 'strong', chance: 0.58, needs: 0.52, edge: 6, paused: true });
  assert.deepEqual([paused.tier, paused.word], ['pass', 'Paused']);
  assert.match(paused.detail, /58% our chance/);
  const shrunk = C.gradeOf({ tier: 'lean', view: 'pass', chance: 0.52, needs: 0.53, edge: -1 });
  assert.deepEqual([shrunk.tier, shrunk.word], ['pass', 'No value']);
  assert.equal(C.tierOf({ tier: 'lean' }), 'lean');
  assert.equal(C.tierOf(null), 'none');
  const rows = [{ grade: { tier: 'strong', paused: true } }, { grade: { tier: 'lean' } }];
  assert.equal(rows.sort(C.byGrade)[0].grade.tier, 'lean', 'a paused line sorts below one with value');
});

test('an early exit credit is a loss on the record and zero in units', () => {
  const credited = { kind: 'props', odds: -113, result: 'loss', earlyExit: true };
  const picks = [credited, { kind: 'props', odds: -110, result: 'win' }];
  const r = C.recordOf(picks, 2);
  assert.equal(r.earlyExits, 1);
  assert.deepEqual([r.wins, r.losses], [1, 1], 'the credited pick still lost');
  assert.equal(C.unitsFor(credited), 0, 'the stake came back');
  assert.ok(Math.abs(r.units - 0.909) < 0.001, 'only the winner moves the units');
  assert.equal(C.unitsFor({ ...credited, earlyExit: false }), -1, 'without the credit it is a full unit');
});

// app.js runs in the browser, so nothing here loads it. Parsing it catches a broken
// edit before it reaches the page, where the only symptom is a stuck "Loading" screen.
test('app.js parses', () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const path = require('node:path');
  const source = fs.readFileSync(path.join(__dirname, '..', 'site', 'app.js'), 'utf8');
  assert.doesNotThrow(() => new vm.Script(source), 'site/app.js has a syntax error');
});
