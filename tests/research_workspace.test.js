'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const C=require('../site/core.js');

test('public stat names normalize to stored columns and partial market searches remain useful',()=>{
  assert.equal(C.researchContext('#player/NFL/1?stat=receptions').stat,'rec');
  assert.equal(C.researchContext('#player/NFL/1?stat=carries').stat,'car');
  assert.equal(C.researchContext('#charts?stat=receptions').chartStat,'rec');
  assert.equal(C.researchContext('#trends?stat=carries').trendStat,'car');
  assert.equal(C.researchMatches('yards','Rec yds'),true);
  assert.equal(C.researchMatches('receiving','recYds'),true);
  assert.equal(C.researchMatches('CAR','Carries'),false);
});
