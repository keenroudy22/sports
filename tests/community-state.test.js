'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const C=require('../site/core.js');
globalThis.KRCore=C;
const {model:M}=require('../site/app.js');
test('personal category notes cannot close an unsettled posted ticket',()=>{
 const now=Date.parse('2026-10-21T17:00:00Z');
 const p={id:'community:personal-ticket:fixture',community:true,posted:true,kind:'parlays',
  parlayType:'community',odds:668,book:'FanDuel',kickoff:'2026-10-21T23:00:00Z',
  entryNote:'Personal ticket; separate from Best Bets.'};
 assert.equal(C.pickState(p,now).word,'Posted ticket');
 assert.equal(C.pickState({...p,result:'win'},now).word,'Won');
 assert.equal(C.pickState({...p,status:'withdrawn'},now).word,'Withdrawn');
 assert.equal(C.pickState(p,now+8*3600000).word,'In play');
 assert.equal(C.pickState({...p,community:false},now).word,'Line moved');
});
