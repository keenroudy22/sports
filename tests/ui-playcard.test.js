'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');

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

test('best-bet tickets keep the decision on the face and details in a fold', () => {
  const ticketBody = source.slice(source.indexOf('const ticket ='), source.indexOf('/* ROI at posted prices'));
  assert.match(ticketBody, /<details class="t-more"/);
  assert.match(ticketBody, /opts\.onPage \? ' open' : ''/, 'a dedicated pick page opens Details by default');
  assert.match(ticketBody, /<summary>Details/);
  assert.match(ticketBody, /\$\{plain\}\$\{vm\.statusShort/, 'chance and status stay on the compact face');
  assert.ok(ticketBody.indexOf('${facts}${why}${hist}${chart}${legs}') > ticketBody.indexOf('<summary>Details'));
  assert.doesNotMatch(ticketBody, /meter-labels/, 'the redundant 0 / needs / 100 row is gone');
});

test('ticket hit charts wait for an open Details fold', () => {
  assert.match(source, /if \(!box\.closest\('details:not\(\[open\]\)'\)\) loadPropBox\(box\)/);
  assert.match(source, /el\.matches\('details\.t-more'\).*querySelectorAll\('\[data-prop-history\]'\)\.forEach\(loadPropBox\)/s);
  assert.match(source, /if \(box\.dataset\.loaded\) return;/, 'opening the fold twice does not reload history');
});

test('compact list tickets never render a second detail body', () => {
  const ticketBody = source.slice(source.indexOf('const ticket ='), source.indexOf('/* ROI at posted prices'));
  assert.match(ticketBody, /\$\{compact \? '' : `<details class="t-more"/);
  assert.match(ticketBody, /\$\{compact \? '' : `<details class="t-more"[\s\S]*?<div class="actions">[\s\S]*?<\/div>`\}/,
    'the same compact branch skips both details and deep-link actions');
});

test('delivery detail stays inside the expandable section', () => {
  const ticketBody = source.slice(source.indexOf('const ticket ='), source.indexOf('/* ROI at posted prices'));
  const fold = ticketBody.indexOf('<details class="t-more"');
  const delivery = ticketBody.indexOf('C.deliveryText(pick)');
  const close = ticketBody.indexOf('</details>', fold);
  assert.ok(fold >= 0 && delivery > fold && close > delivery);
});

test('ticket Details controls meet the shared tap target', () => {
  const css = fs.readFileSync('site/app.css', 'utf8');
  assert.match(css, /\.ticket \.t-more > summary[^}]*min-height: var\(--tap\)/);
  assert.match(css, /\.ticket \.t-more\[open\] > summary::after \{ content: '▴'; \}/);
});
