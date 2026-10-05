'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');
const now = Date.parse('2026-10-04T14:00:00Z');
const row = {player:'Player',team:{name:'Team'},matchup:'Team at Rival',league:'NFL',gameId:'NFL-1',
  kind:'milestone',stat:'rec',games:10,hits:8,kickoff:'2026-10-04T17:00:00Z'};
test('exact hit counts control rate filters; rounded rates never manufacture 100%', () => {
  assert.equal(C.filterTrends([row],{rate:80},now).length,1);
  assert.equal(C.filterTrends([row],{rate:90},now).length,0);
  assert.equal(C.filterTrends([{...row,games:1000,hits:999,rate:100}],{rate:100},now).length,0);
  assert.equal(C.filterTrends([{...row,hits:10}],{rate:100},now).length,1);
});
test('filter stat, sample, team, game, league and stale prices', () => {
  for (const f of [{stat:'car'},{min:11},{query:'nope'},{league:'CFB'},{game:'NFL-2'},{kind:'alternate'}])
    assert.equal(C.filterTrends([row],f,now).length,0);
  assert.equal(C.filterTrends([row],{query:'rival'},now).length,1);
  assert.equal(C.filterTrends([{...row,kind:'main',observedAt:'2026-10-04T08:00:00Z'}],{},now).length,0);
  assert.equal(C.filterTrends([row],{},Date.parse(row.kickoff)).length,0);
  assert.deepEqual(C.parseRoute('#trends/NFL-1'),{view:'trends',id:'NFL-1'});
});
test('history windows recalculate exact hit rates from the newest games', () => {
  const base = {...row, direction:'over', line:10, history:[5, 11, 12, 7, 15, 16].map((value, i) => ({date:`2026-09-0${i + 1}`,value}))};
  const season = C.trendWindow([base], 'season')[0];
  const last5 = C.trendWindow([base], 'last5')[0];
  const last10 = C.trendWindow([base], 'last10')[0];
  assert.deepEqual([season.hits, season.games, season.rate], [4, 6, 66.7]);
  assert.deepEqual([last5.hits, last5.games, last5.rate], [4, 5, 80]);
  assert.deepEqual([last10.hits, last10.games, last10.rate], [4, 6, 66.7]);
  assert.equal(last5.history[0].value, 11, 'Last 5 uses the newest five stored appearances');
  const under = C.trendWindow([{...base, direction:'under', line:11}], 'season')[0];
  assert.deepEqual([under.hits, under.pushes], [2, 1]);
  const milestone = C.trendWindow([{...base, direction:'at-least', line:11}], 'season')[0];
  assert.deepEqual([milestone.hits, milestone.pushes], [4, 0]);
});
test('duplicate book offers collapse to the best current price', () => {
  const offers = [{...row, athleteId:'1', stat:'rec', direction:'over', line:3.5, kind:'main', odds:-115, book:'FanDuel'},
    {...row, athleteId:'1', stat:'rec', direction:'over', line:3.5, kind:'main', odds:-105, book:'DraftKings'},
    {...row, athleteId:'1', stat:'rec', direction:'over', line:4.5, kind:'main', odds:120, book:'FanDuel'}];
  const best = C.bestTrendPrices(offers);
  assert.equal(best.length, 2);
  assert.equal(best.find(r => r.line === 3.5).book, 'DraftKings');
});
