'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../site/personal.js');
const now=Date.parse('2026-10-05T15:00:00Z');
const row={league:'NFL',gameId:'NFL-1',athleteId:'7',market:'rec',direction:'over',book:'FanDuel',line:4.5,odds:-110,observedAt:'2026-10-05T14:00:00Z',kickoff:'2026-10-05T20:00:00Z',state:'open'};
test('saving preserves original evidence and never mixes books or sides',()=>{
 const saved=P.snapshot(row,now);
 assert.equal(saved.line,4.5);
 assert.equal(P.changes(saved,[{...row,book:'DraftKings',line:5.5}],now).state,'unavailable');
 assert.equal(P.changes(saved,[{...row,direction:'under'}],now).state,'unavailable');
 assert.equal(P.changes(saved,[{...row,market:'rushYds'}],now).state,'unavailable');
 assert.equal(P.changes(saved,[{...row,line:5.5}],now).state,'changed');
 assert.equal(P.changes(saved,[row],now).state,'same');
 assert.equal(saved.line,4.5);
});
test('stale, future and started quotes are not live changes',()=>{
 const saved=P.snapshot(row,now);
 for(const r of [{...row,state:'closed'},{...row,observedAt:'2026-10-04T00:00:00Z'},{...row,observedAt:'2026-10-06T00:00:00Z'}]) assert.equal(P.changes(saved,[r],now).state,'unavailable');
 assert.equal(P.changes(saved,[row],Date.parse('2026-10-06T00:00:00Z')).state,'started');
});
test('sport changes preserve the selected section, with detail pages returning to their parent',()=>{
 for(const view of ['today','games','stats','record','lab','board','saved']) assert.equal(P.sportRoute({view},'MLB'),null);
 assert.equal(P.sportRoute({view:'scores'},'NBA'),'#scores/NBA');
 assert.equal(P.sportRoute({view:'player'},'NBA'),'#stats');
 assert.equal(P.sportRoute({view:'game'},'NBA'),'#games');
 assert.equal(P.league('bogus'),'ALL');
});
