'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');

test('legacy route table lands on an equivalent preview view', () => {
  const table = [
    ['', 'today'], ['#sports', 'today'], ['#digest', 'today'], ['#board', 'research'], ['#board/props', 'research'],
    ['#board/favorites', 'research'], ['#lines', 'research'], ['#props', 'research'], ['#trends', 'research'],
    ['#stats', 'research'], ['#stats/defense', 'research'], ['#charts', 'research'], ['#players', 'research'],
    ['#defense', 'research'], ['#games', 'games'], ['#scores/NHL', 'games'], ['#sport/NBA', 'games'],
    ['#results', 'record'], ['#model', 'record'], ['#tools', 'more'], ['#parlays', 'ticket'],
  ];
  for (const [hash, view] of table) assert.equal(M.resolve(hash).view, view, hash);
});

test('shared legacy filters survive route resolution', () => {
  const players = M.resolve('#stats?stat=recYds&sample=last5&date=next&position=WR&q=Bijan&sport=NFL');
  assert.equal(players.mode, 'players');
  assert.deepEqual({ stat: players.ctx.chartStat, sample: players.ctx.chartWindow, day: players.ctx.chartDay, pos: players.ctx.chartPos, q: players.ctx.researchQuery, league: players.ctx.league },
    { stat: 'recYds', sample: 'last5', day: 'next', pos: 'WR', q: 'Bijan', league: 'NFL' });
  const trends = M.resolve('#trends?stat=rushYds&sample=last10&date=today&rate=90&kind=main&q=Henry&sport=NFL');
  assert.deepEqual({ stat: trends.ctx.trendStat, sample: trends.ctx.trendWindow, day: trends.ctx.trendDay, rate: trends.ctx.trendRate, kind: trends.ctx.trendKind, q: trends.ctx.researchQuery },
    { stat: 'rushYds', sample: 'last10', day: 'today', rate: '90', kind: 'main', q: 'Henry' });
});

test('bare Research preserves the old news desk and legacy player searches land on Search', () => {
  assert.equal(M.resolve('#research').mode, 'news');
  assert.equal(M.resolve('#research/lines').mode, 'lines');
  assert.equal(M.resolve('#stats/search').sub, 'search');
  assert.equal(M.resolve('#stats/players').sub, 'search');
});

test('canonical table rewrites legacy pages and never rewrites public deep links', () => {
  const table = [
    ['#board/props', '#research/lines?type=props'], ['#board/favorites', '#research/lines?sort=edge'],
    ['#trends', '#research/trends'], ['#scores/NHL', '#games/live?sport=NHL'],
    ['#results', '#record'], ['#model', '#record/model'],
  ];
  for (const [oldHash, nextHash] of table) assert.equal(M.canonical(M.resolve(oldHash)), nextHash, oldHash);
  for (const hash of ['#pick/a/b', '#game/CFB-1', '#player/NFL/9', '#team/CFB/3']) assert.equal(M.canonical(M.resolve(hash)), null, hash);
});
