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
