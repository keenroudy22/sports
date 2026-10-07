'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');

test('the research board admits only current open priced rows before kickoff', () => {
  const now = Date.parse('2026-10-06T20:00:00Z');
  const base = { state: 'open', odds: -110, book: 'FanDuel', kickoff: '2026-10-07T00:00:00Z' };
  assert.equal(M.onBoard(base, now), true);
  for (const row of [{ ...base, state: 'closed' }, { ...base, odds: null }, { ...base, book: null }, { ...base, kickoff: '2026-10-06T19:00:00Z' }]) assert.ok(!M.onBoard(row, now));
  assert.match(source, /onBoard\(vm, now\) && current\(vm\)/, 'Today and Research retain the four-hour current-quote filter');
});

test('best price compares books at the exact same line only', () => {
  const row = { id: 'r', title: 'P over 224.5 passing yards', athleteId: '9', gameId: 'CFB-1', market: 'passYds', line: 224.5,
    odds: -114, book: 'FanDuel', state: 'open', kickoff: '2099-01-01T00:00:00Z', observedAt: new Date().toISOString(),
    books: [{ book: 'FanDuel', line: 224.5, odds: -114 }, { book: 'DraftKings', line: 224.5, odds: -105 }, { book: 'theScore Bet', line: 199.5, odds: 120 }],
    grade: { chance: 0.56, needs: 0.533, edge: 2.7, tier: 'lean', calibrated: true } };
  const vm = M.lineVM(row);
  assert.deepEqual([vm.bestBook, vm.bestOdds, vm.booksCount], ['DraftKings', -105, 2]);
  assert.deepEqual(vm.otherLines, [{ book: 'theScore Bet', line: 199.5, odds: 120 }]);
});

test('Best bet matching requires the same game, player, stat and side', () => {
  const pick = { gameId: 'NFL-1', athleteId: '9', market: 'rec', direction: 'over' };
  assert.equal(M.officialKey(pick), M.officialKey({ gameId: 'NFL-1', athleteId: '9', market: 'receptions', direction: 'OVER' }));
  for (const row of [
    { gameId: 'NFL-2', athleteId: '9', market: 'rec', direction: 'over' },
    { gameId: 'NFL-1', athleteId: '8', market: 'rec', direction: 'over' },
    { gameId: 'NFL-1', athleteId: '9', market: 'recYds', direction: 'over' },
    { gameId: 'NFL-1', athleteId: '9', market: 'rec', direction: 'under' },
  ]) assert.notEqual(M.officialKey(pick), M.officialKey(row));
});
