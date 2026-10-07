'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');

test('model-only support requires a saved for-direction fact', () => {
  const pick={modelLean:true,reason:'Defensive starters are out.',why:'Defensive starters are out.'};
  assert.deepEqual(M.whyLines(pick),[]);
  assert.deepEqual(M.whyLines({...pick,reasoning:{context:['Both teams rank in the top 10 for pace.'],cautions:['Defensive starters are out.']}}),['Both teams rank in the top 10 for pace.']);
});

test('Good-to prices and current quotes retain the published cutoff', () => {
  const now=Date.parse('2026-10-07T12:00:00Z');
  const pick={gameId:'NFL-1',market:'total points',direction:'over',line:49.5,odds:-110,book:'FanDuel',
    cutoffOdds:-119,cutoffLine:49.5,cutoffBoundary:51.5,kickoff:'2026-10-08T00:00:00Z'};
  const row={...pick,state:'open',observedAt:'2026-10-07T11:30:00Z'};
  assert.equal(M.goodTo(pick),'Good to -119 at 49.5');
  assert.equal(M.latestPickQuote(pick,[row],now).inside,true);
  assert.equal(M.latestPickQuote(pick,[{...row,odds:-120}],now).inside,false);
  assert.equal(M.latestPickQuote(pick,[{...row,line:51.5}],now).inside,false);
  assert.equal(M.latestPickQuote(pick,[{...row,observedAt:'2026-10-06T00:00:00Z'}],now),null);
  assert.match(source,/ago\(latest.current.observedAt\)/);
});

test('history and defense cannot manufacture Model support below the price bar', () => {
  const hurst = { chance: .52, needs: .533, edge: -1.3, clearsPrice: false };
  assert.equal(M.matchupSignals(hurst, true, true), 2);
  assert.equal(M.matchupSignals({...hurst, clearsPrice:true}, true, true), 3);
  assert.match(M.researchPrice(hurst), /52% vs 53% needed.*no edge/);
  assert.match(source, /x\.r\.clearsPrice === true/);
  assert.match(source, /History only · no edge at this price/);
});

test('a research price check matches the exact market, side, number, book and fresh quote', () => {
  const now=Date.parse('2026-10-07T12:00:00Z');
  const row={gameId:'CFB-1',athleteId:'9',stat:'passYds',market:'passing yards',direction:'under',line:211.5,odds:-110,book:'FanDuel'};
  const line={...row,state:'open',observedAt:'2026-10-07T11:00:00Z',grade:{chance:.58}};
  assert.equal(M.priceMatch(row,[line],now),line);
  for(const changed of [{line:210.5},{direction:'over'},{book:'DraftKings'},{odds:-115},{observedAt:'2026-10-06T00:00:00Z'}])
    assert.equal(M.priceMatch(row,[{...line,...changed}],now),null);
  assert.match(M.averageGap(167.1,[50,36,43,11].map(x=>x*266.3/35)),/167.1.*266.3.*Wide range/);
  assert.equal(M.averageGap(35,[30,40]),'');
});

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

test('provider identity stays internal while the board uses the separate display name', () => {
  const row = { id: 'r2', title: 'A at B over 50.5', gameId: 'CFB-2', market: 'total points', direction: 'over', line: 50.5,
    odds: -110, book: 'ESPN BET', displayBook: 'theScore Bet', state: 'open', kickoff: '2099-01-01T00:00:00Z', observedAt: new Date().toISOString(),
    books: [{ book: 'ESPN BET', displayBook: 'theScore Bet', line: 50.5, odds: -110 }],
    bestSameLine: { book: 'ESPN BET', displayBook: 'theScore Bet', odds: -110 }, grade: {} };
  const vm = M.lineVM(row);
  assert.equal(vm.book, 'theScore Bet');
  assert.equal(vm.bestBook, 'theScore Bet');
  assert.equal(vm.src.book, 'ESPN BET');
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

test('a defense rank colors only when it supports or works against the side of the bet', () => {
  assert.equal(M.defenseVerdict('soft', 'under', 4), 'opposes');
  assert.equal(M.defenseVerdict('tough', 'under', 4), 'supports');
  assert.equal(M.defenseVerdict('soft', 'OVER', 4), 'supports');
  assert.equal(M.defenseVerdict('tough', 'over', 4), 'opposes');
  assert.equal(M.defenseVerdict('soft', 'over', 2), null, 'three games minimum');
  assert.equal(M.defenseVerdict('neutral', 'over', 9), null);
  assert.match(source, /defenseWords\(teams, opp\.id, data\.pos, stat, league, side\)/, 'ticket hit charts pass the bet side');
});

test('every core helper the page calls exists, so Today redraws once the full record loads', () => {
  const missing = [...new Set([...source.matchAll(/(?<![\w.$])C\.([A-Za-z_$][\w$]*)/g)].map(m => m[1]))].filter(n => !(n in globalThis.KRCore));
  assert.deepEqual(missing, []);
  assert.match(source, /if \(C\.parseRoute\(location\.hash\)\.view === 'today'\) render\(true\)/);
});

test('the college defense file name keeps its .json extension and cannot climb directories', () => {
  const m = source.match(/String\(teams\.defenseFile\)\.replace\((\/.+?\/gi), ''\)/);
  assert.ok(m, 'defense file sanitizer present');
  const re = eval(m[1]);
  assert.equal('teams/CFB-defense.json'.replace(re, ''), 'teams/CFB-defense.json');
  assert.ok(!'../../x.json'.replace(re, '').includes('..'));
});
