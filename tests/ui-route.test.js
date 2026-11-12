'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');

test('Today shortcuts keep their scroll destination through the app router', () => {
  for (const anchor of ['today-card','today-climb','today-posted-straights','cbb-picks']) {
    assert.deepEqual(M.resolve('#'+anchor),{view:'today',anchor});
  }
  assert.equal(M.resolve('#not-a-posted-ticket').anchor,undefined);
});

test('legacy route table lands on an equivalent preview view', () => {
  const table = [
    ['', 'today'], ['#sports', 'today'], ['#digest', 'today'], ['#board', 'research'], ['#board/props', 'research'],
    ['#board/favorites', 'research'], ['#lines', 'research'], ['#props', 'research'], ['#trends', 'research'],
    ['#stats', 'research'], ['#stats/defense', 'research'], ['#charts', 'research'], ['#players', 'research'],
    ['#defense', 'research'], ['#games', 'games'], ['#scores/NHL', 'games'], ['#sport/NBA', 'games'],
    ['#results', 'record'], ['#model', 'record'], ['#tools', 'more'], ['#responsible', 'more'], ['#parlays', 'ticket'],
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
  assert.equal(M.resolve('#research?type=props').mode, 'lines');
  assert.equal(M.resolve('#research?sort=edge&show=value&q=Bijan').mode, 'lines');
  assert.equal(M.resolve('#research/lines').mode, 'lines');
  assert.equal(M.resolve('#stats/search').sub, 'search');
  assert.equal(M.resolve('#stats/players').sub, 'search');
  assert.equal(M.resolve('#stats?stat=recYds&sample=last5&q=Bijan').sub, null,
    'a copied matchup-chart filter reopens Matchups, not the Search list');
});

test('canonical table rewrites legacy pages and never rewrites public deep links', () => {
  const table = [
    ['#board/props', '#research/lines?type=props'], ['#board/favorites', '#research/lines?sort=edge'],
    ['#trends', '#research/trends'], ['#scores/NHL', '#games/live?sport=NHL'],
    ['#results', '#record'], ['#model', '#record/model'], ['#responsible', '#more'],
  ];
  for (const [oldHash, nextHash] of table) assert.equal(M.canonical(M.resolve(oldHash)), nextHash, oldHash);
  for (const hash of ['#pick/a/b', '#game/CFB-1', '#player/NFL/9', '#team/CFB/3']) assert.equal(M.canonical(M.resolve(hash)), null, hash);
});

test('Results defaults to all sports and preserves only an explicit sport filter', () => {
  assert.deepEqual(M.resolve('#record'), { view: 'record', tab: 'official', anchor: null, league: null });
  assert.deepEqual(M.resolve('#record/calendar?sport=CFB'), { view: 'record', tab: 'official', anchor: 'calendar', league: 'CFB' });
  assert.deepEqual(M.resolve('#record/fun?sport=NFL'), { view: 'record', tab: 'fun', anchor: null, league: 'NFL' });
  assert.equal(M.canonical(M.resolve('#results?sport=CFB')), '#record?sport=CFB');
});

test('player-prop navigation follows every supported sport instead of falling back to NFL', () => {
  for (const sport of ['NFL', 'CFB', 'NBA', 'CBB']) {
    assert.equal(M.propSport(sport), sport);
    assert.equal(M.propsHref(sport), `#research/players?sport=${sport}`);
  }
  assert.equal(M.propsHref('ALL'), '#research/players?sport=NFL');
  assert.equal(M.propsHref('NHL'), '#research/players?sport=NFL');
});
