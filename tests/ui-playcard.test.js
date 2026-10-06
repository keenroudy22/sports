'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/next/app.js');
const source = fs.readFileSync('site/next/app.js', 'utf8');

const base = {
  id: 'x', kind: 'props', league: 'NFL', gameId: 'NFL-1', athleteId: '9', market: 'recYds',
  displayTitle: 'Player over 49.5 receiving yards', line: 49.5, direction: 'over', odds: -110,
  book: 'FanDuel', kickoff: '2099-01-01T00:00:00Z', status: 'active',
  probabilityAtPublication: { chance: 0.56, breakEven: 0.524, edgePoints: 3.6, calibrated: true },
};

test('Today renders Pick of the Day, then Climb, then remaining best bets', () => {
  const body = source.slice(source.indexOf('const heroList ='), source.indexOf('const graded =', source.indexOf('const heroList =')));
  const potd = body.indexOf('potd.map');
  const climb = body.indexOf('climbOpen');
  const rest = body.indexOf('rest.map');
  assert.ok(potd >= 0 && climb > potd && rest > climb, body);
});

test('expired prices are standing plays but never look open', () => {
  const vm = M.pickVM({ ...base, expiresAt: '2026-10-01T00:00:00Z' }, Date.parse('2026-10-06T00:00:00Z'));
  assert.equal(vm.mode, 'expired');
  assert.equal(vm.stub.cls, 'closed');
  assert.equal(vm.stub.small, 'at posted price');
  assert.doesNotMatch([vm.status, vm.statusNote, vm.stub.small].join(' '), /\bopen\b|price expired/i);
});

test('closed, pulled and withdrawn states cannot receive the pitch or meter', () => {
  const now = Date.parse('2026-10-06T00:00:00Z');
  const rows = [
    { ...base, entryNote: 'Closed to new entries at 11:45 AM ET: line moved.' },
    { ...base, entryNote: 'Pulled over news before its post went out.' },
    { ...base, status: 'withdrawn' },
  ].map(row => M.pickVM(row, now));
  assert.ok(rows.every(vm => vm.mode === 'closed' && vm.stub.cls === 'closed'));
  const ticketBody = source.slice(source.indexOf('const ticket ='), source.indexOf('/* ROI at posted prices'));
  assert.match(ticketBody, /plain = priced && vm\.mode === 'open'/);
  assert.match(ticketBody, /vm\.mode !== 'closed'/);
  assert.match(ticketBody, /why = !compact && vm\.mode !== 'closed'/);
});

test('the raw projection stays off the ticket and inside How we got this', () => {
  const ticketBody = source.slice(source.indexOf('const ticket ='), source.indexOf('/* ROI at posted prices'));
  const explanation = source.slice(source.indexOf('const howWeGotIt ='), source.indexOf('/* A best bet', source.indexOf('const howWeGotIt =')));
  assert.doesNotMatch(ticketBody, /pick\.projection|vm\.projection/);
  assert.match(explanation, /pick && pick\.projection/);
  assert.match(M.howWeGotIt({ projection: 61.2, line: 49.5, odds: -110, probabilityAtPublication: { chance: 0.56 } }).join(' '), /61\.2 against the 49\.5 line/);
});
