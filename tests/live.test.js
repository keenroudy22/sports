const {test} = require('node:test');
const assert = require('node:assert/strict');
const L = require('../site/live.js');
test('pregame quotes preserve exact side/line/price and never appear in play',()=>{
  const c={odds:[{provider:{name:'DraftKings'},moneyline:{home:{close:{odds:'-192'}}},pointSpread:{away:{close:{line:'+1.5',odds:'-155'}}},total:{over:{close:{line:'o5.5',odds:'-122'}}}}]};
  assert.deepEqual(L.pregameOdds(c,'scheduled').rows,[{side:'home',market:'ML',price:-192},{side:'away',market:'Spread',line:1.5,price:-155},{side:'over',market:'Total',line:5.5,price:-122}].sort((a,b)=>['away','home','over'].indexOf(a.side)-['away','home','over'].indexOf(b.side)));
  assert.equal(L.pregameOdds(c,'in_progress'),null);assert.equal(L.pregameOdds(c,'final'),null);
  assert.equal(L.pregameOdds({odds:[]},'scheduled'),null);
});
test('score cache is nonblocking, deduplicates and backs off failed requests without faking freshness', async () => {
  let clock=100000,calls=0,fail=false;
  const c=L.createCache({now:()=>clock,fetcher:async()=>{calls++; if(fail) throw Error('offline'); return {ok:true,json:async()=>({events:[{id:1}]})};}});
  assert.equal(c.read('a','url',x=>x),null);
  c.read('a','url',x=>x); await c.pending.get('a');
  assert.equal(calls,1); assert.equal(c.rows.get('a').at,100000);
  clock+=46000;fail=true;c.read('a','url',x=>x); await c.pending.get('a');
  const stale=c.read('a','url',x=>x);
  assert.equal(calls,2);assert.equal(stale.at,100000);assert.equal(stale.failed,true);
  assert.equal(L.freshness(stale,clock),'stale');assert.equal(stale.games.length,1);
  c.read('never','url',x=>x);await c.pending.get('never');
  assert.equal(L.freshness(c.rows.get('never'),clock),'unavailable');
});
test('new games enter the browser and midnight remains Eastern',()=>{
  assert.equal(L.dayOf('2026-10-05T02:30:00Z'),'2026-10-04');
  const g={providerId:'new',kickoff:'2026-10-05T02:30:00Z',teams:{home:{score:2},away:{score:1}}};
  const rows=L.mergeGames([],{at:100000,games:[g]},'2026-10-04');
  assert.equal(rows.length,1);assert.equal(rows[0].scores.home,2);
  assert.equal(L.mergeGames([],{at:100000,games:[g]},'2026-10-05').length,0);
});
