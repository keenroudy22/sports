'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');

// [eventId, date, provider season, week, season type, team, opponent, home, ...stats]
const row = (id, date, season, value, type = 2) => [id, date, season, 1, type, 'a', 'b', 1, value];

test('player history defaults to the provider current season, not calendar year or latest player appearance', () => {
  const rows = [row('jan', '2026-01-04', 2025, 150), row('prior', '2025-12-28', 2025, 120),
    row('current', '2026-09-06', 2026, 230), row('playoff', '2026-01-11', 2025, 300, 3)];
  assert.deepEqual(C.playerHistory(rows, 2026).map(r => r[0]), ['current']);
  assert.deepEqual(C.playerHistory(rows, 2025).map(r => r[0]), ['prior', 'jan'], 'January belongs to its saved football season');
  assert.deepEqual(C.playerHistory(rows.slice(0, 2), 2026), [], 'no current games does not silently fall back to an old season');
});

test('older seasons require an explicit year or All selection; postseason stays excluded', () => {
  const rows = [row('old', '2024-10-05', 2024, 0), row('prior', '2025-09-06', 2025, 11),
    row('post', '2025-12-30', 2025, 99, 3), row('now', '2026-09-05', 2026, 46)];
  assert.deepEqual(C.playerHistory(rows, 2026, 'all').map(r => r[0]), ['old', 'prior', 'now']);
  assert.deepEqual(C.playerHistory(rows, 2026, '2025').map(r => r[0]), ['prior']);
  assert.deepEqual(C.playerHistory(rows, 2026, 2024).map(r => r[0]), ['old']);
});

test('player windows apply after season and exclusive game-date cutoff, without importing old games', () => {
  const rows = [row('old', '2025-09-30', 2025, 900), ...Array.from({length: 8}, (_, i) =>
    row(String(i + 1), `2026-09-${String(i + 1).padStart(2, '0')}`, 2026, i + 1))].reverse();
  assert.deepEqual(C.playerHistory(rows, 2026, 'current', 'last5', '2026-09-07T20:00:00Z').map(r => r[0]), ['2', '3', '4', '5', '6']);
  assert.deepEqual(C.playerHistory(rows, 2026, 'current', 'last10', '2026-09-03').map(r => r[0]), ['1', '2']);
  assert.equal(C.playerHistory(rows, 2026, 'current', 'last20').length, 8);
});

test('player history preserves zero, negative and unknown observations and does not mutate stored rows', () => {
  const rows = [row('late', '2026-09-20', 2026, null), row('early', '2026-09-06', 2026, -2), row('zero', '2026-09-13', 2026, 0)];
  const snapshot = JSON.stringify(rows);
  const result = C.playerHistory(rows, 2026);
  assert.deepEqual(result.map(r => r[8]), [-2, 0, null]);
  assert.notEqual(result, rows);
  assert.equal(JSON.stringify(rows), snapshot);
  assert.equal(C.playerHistory(Array.from({length: 25}, (_, i) => row(String(i), `2026-09-${String(i + 1).padStart(2, '0')}`, 2026, i)), 2026).length, 25,
    'the full selected season is not silently capped at 20 games');
});

test('Landry Lyddy regression: current season excludes backup appearances from 2023–2025', () => {
  const values = [2, 51, 68, 0, 0, 11, 0, 128, 267, 46, 25, 194, 243];
  const dates = ['2023-10-07', '2023-10-14', '2023-10-21', '2024-10-05', '2024-11-02', '2025-09-06', '2025-09-13',
    '2025-11-08', '2025-11-15', '2026-09-05', '2026-09-12', '2026-09-19', '2026-09-26'];
  const rows = values.map((value, i) => row(String(i), dates[i], Number(dates[i].slice(0, 4)), value));
  const current = C.playerHistory(rows, 2026).map(r => r[8]);
  assert.deepEqual(current, [46, 25, 194, 243]);
  assert.deepEqual(C.hits(current, 206.5), {over: 1, under: 3, push: 0, n: 4});
  assert.equal(C.summarize(current).avg, 127);
  assert.equal(C.playerHistory(rows, 2026, 'all').length, 13);
});
