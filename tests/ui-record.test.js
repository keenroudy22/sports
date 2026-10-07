'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const C = require('../site/core.js');
globalThis.KRCore = C;
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');

const picks = [
  { id: 'a', kind: 'props', odds: -110, result: 'win', settledAt: '2026-09-01T01:00:00Z' },
  { id: 'b', kind: 'gamePicks', odds: 120, result: 'loss', settledAt: '2026-09-02T01:00:00Z' },
  { id: 'c', kind: 'props', odds: -110, result: 'push', settledAt: '2026-09-03T01:00:00Z' },
  { id: 'd', kind: 'props', odds: -110, result: 'win', priceAssumed: true, settledAt: '2026-09-04T01:00:00Z' },
  { id: 'e', kind: 'parlays', odds: 500, result: 'win', legs: ['A', 'B'], settledAt: '2026-09-05T01:00:00Z' },
];

test('Record headline is the shared core recordBreakdown, not separate UI math', () => {
  const rec = C.recordBreakdown(picks.filter(p => !C.isParlay(p)));
  assert.deepEqual([rec.all.wins, rec.all.losses, rec.all.pushes], [2, 1, 1]);
  const kpi = source.slice(source.indexOf('const kpiStrip ='), source.indexOf('const plainRecord', source.indexOf('const kpiStrip =')));
  assert.match(kpi, /const rec = C\.recordBreakdown\(straight\)/);
  assert.match(kpi, /wl\(rec\.all\)/);
  assert.doesNotMatch(kpi, /summarizePicks\(straight\)/);
});

test('season chart ends at captured-price units exactly', () => {
  const straight = picks.filter(p => !C.isParlay(p));
  const rec = C.recordBreakdown(straight);
  const points = M.cumulativeUnits(straight, C.unitsFor);
  assert.ok(points.length > 0);
  assert.equal(points.at(-1).units, Math.round(rec.captured.units * 100) / 100);
  const recordView = moreSource.slice(moreSource.indexOf("if (tab === 'official')"), moreSource.indexOf("if (tab === 'fun')"));
  assert.match(recordView, /const points = cumulativeUnits\(straight, C\.unitsFor\)/);
  assert.match(recordView, /unitsChart\(points\)/);
  assert.match(recordView, /units\(rec\.captured\.units\)/);
});

test('Model restores projected-winner and fun-ticket scorecard tiles', () => {
  const modelView = moreSource.slice(moreSource.indexOf("if (tab === 'model')"), moreSource.indexOf('/* Trials:', moreSource.indexOf("if (tab === 'model')")));
  assert.match(modelView, /<small>Projected winners<\/small>/);
  assert.match(modelView, /card\.moneyline/);
  assert.match(modelView, /<small>Fun tickets<\/small>/);
  assert.match(modelView, /card\.parlays/);
});
