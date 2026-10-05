const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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
test('notes escape source text and stay below official plays without an empty filler card', () => {
  const source = fs.readFileSync('site/app.js','utf8');
  const body = source.match(/const deskNotesSection = \(data, games, league\) => \{([\s\S]*?)\n  \};/)[1];
  const render = new Function('C','esc','whenShort','section','data','games','league',body);
  const core = {...C,deskNotes: () => [{...row,title:'<script>x</script>',label:'Season trend'}]};
  const html = render(core,C.esc,C.whenShort,(title,body,aside)=>title+body+aside,{},[],'ALL');
  assert.match(html,/&lt;script&gt;/);
  assert.doesNotMatch(html,/<script>/);
  assert.match(html,/Research, not posted plays/);
  assert.equal(render({...C,deskNotes:()=>[]},C.esc,C.whenShort,()=>'',{},[],'ALL'),'');
  assert.ok(source.indexOf('section("Today\'s plays"') < source.indexOf('deskNotesSection(notes, games'));
});
