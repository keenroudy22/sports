const { test } = require('node:test');
const assert = require('node:assert/strict');
const C = require('../site/core.js');
const now = Date.parse('2026-10-05T12:00:00Z');
const row = {gameId:'NFL-1',league:'NFL',title:'Player',text:'3/4 recorded games',
  href:'#game/NFL-1',observedAt:'2026-10-05T11:00:00Z',expiresAt:'2026-10-05T15:00:00Z',kickoff:'2026-10-06T00:00:00Z'};
const game = {id:'NFL-1',state:'pre'};
const data = rows => ({schemaVersion:1,rows});
test('homepage notes hide expired, started, missing, future, wrong-league and unsafe stories', () => {
  assert.equal(C.deskNotes(data([row]),'ALL',now,[game]).length,1);
  for(const r of [{...row,expiresAt:'2026-10-05T11:00Z'}, {...row,kickoff:'2026-10-05T11:00Z'},
    {...row,observedAt:'2026-10-05T13:00Z'}, {...row,href:'javascript:alert(1)'}]) {
    assert.equal(C.deskNotes(data([r]),'ALL',now,[game]).length,0);
  }
  assert.equal(C.deskNotes(data([row]),'CFB',now,[game]).length,0);
  assert.equal(C.deskNotes(data([row]),'ALL',now,[]).length,0);
  assert.equal(C.deskNotes(data([row]),'ALL',now,[{...game,state:'in'}]).length,0);
  assert.equal(C.deskNotes(null,'ALL',now,[game]).length,0);
  assert.equal(C.deskNotes(data([{...row,league:'CBB',href:'#scores/CBB'}]),'ALL',now,[]).length,1);
});
