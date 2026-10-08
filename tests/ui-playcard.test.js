'use strict';
/* The Kitchen Ticket (OWNER-DECISIONS 2026-10-07 item 22): what a ticket may say in each state. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
globalThis.KRCore = require('../site/core.js');
const { model: M } = require('../site/app.js');
const source = fs.readFileSync('site/app.js', 'utf8');
const ticketBody = source.slice(source.indexOf('  const ticket = (pick, opts = {}) =>'), source.indexOf('  const rail = (rows'));

const base = {
  id: 'x', kind: 'props', league: 'NFL', gameId: 'NFL-1', athleteId: '9', market: 'recYds',
  displayTitle: 'Player over 49.5 receiving yards', line: 49.5, direction: 'over', odds: -110,
  book: 'FanDuel', kickoff: '2099-01-01T00:00:00Z', status: 'active',
  probabilityAtPublication: { chance: 0.56, breakEven: 0.524, edgePoints: 3.6, calibrated: true },
};

test('expired prices are standing plays but never look open', () => {
  const vm = M.pickVM({ ...base, expiresAt: '2026-10-01T00:00:00Z' }, Date.parse('2026-10-06T00:00:00Z'));
  assert.equal(vm.mode, 'expired');
  assert.doesNotMatch([vm.status, vm.statusNote].join(' '), /\bopen\b|price expired/i);
  assert.match(ticketBody, /vm\.mode === 'expired' \? 'Posted price may be gone\. Check your book\.'/);
  assert.match(ticketBody, /const tense = !afterHold && \(vm\.mode === 'open' \|\| \(vm\.mode === 'expired' && latest && latest\.inside\)\)/,
    'an aged quote only reads "I have it" while a fresh quote is still inside the posted limit; a later hold is historical');
});

test('closed, pulled and withdrawn states get their state words, never "Still good to"', () => {
  const now = Date.parse('2026-10-06T00:00:00Z');
  const rows = [
    { ...base, entryNote: 'Closed to new entries at 11:45 AM ET: line moved.' },
    { ...base, entryNote: 'Pulled over news before its post went out.' },
    { ...base, status: 'withdrawn' },
  ].map(row => M.pickVM(row, now));
  assert.ok(rows.every(vm => vm.mode === 'closed'));
  assert.match(ticketBody, /: vm\.mode === 'open' \? good : vm\.mode === 'expired' \? 'Posted price may be gone\. Check your book\.' : vm\.statusShort \|\| vm\.status \|\| ''/);
});

test('the raw projection, fair price and edge stay off the ticket', () => {
  assert.doesNotMatch(ticketBody, /pick\.projection|vm\.projection|vm\.fair|vm\.edge|fairOdds/);
  const explanation = source.slice(source.indexOf('const howWeGotIt ='), source.indexOf('/* A best bet', source.indexOf('const howWeGotIt =')));
  assert.match(explanation, /pick && pick\.projection/);
  const pickPage = source.slice(source.indexOf('VIEWS.pick = async'), source.indexOf('/* ---------- Research'));
  assert.match(pickPage, /tape\('My price'/, 'fair price and edge live on the play page');
  assert.match(pickPage, /Price matching our chance/);
});

test('WHY and BUT are the build\'s saved strings, printed as they are', () => {
  assert.match(ticketBody, /say\('WHY', heldSafe\(pick\.ticketWhy, hold\)\) \+ say\('BUT', heldSafe\(pick\.ticketBut, hold\), ' kt-but'\)/);
  assert.match(ticketBody, /const heldSafe = \(text, held\) => held && !held\.afterPosting && HELD_WORDS\.test\(text \|\| ''\) \? null : text;/,
    'a new hold drops suspect words before posting; a delivered play retains its posted WHY');
  assert.doesNotMatch(ticketBody, /whyLines|watchLine|reasoning\.|cautions/);
});

test('delivery detail, notes, cutoff and sources stay on the play page', () => {
  const pickPage = source.slice(source.indexOf('VIEWS.pick = async'), source.indexOf('/* ---------- Research'));
  for (const piece of ['C.deliveryText(pick)', "Our notes when we posted it", 'Was good to', 'Sources:', 'data-prop-history', 'data-watch-pick'])
    assert.ok(pickPage.includes(piece), piece);
});

test('ticket hit charts load once, on the play page, when visible', () => {
  assert.match(source, /if \(!box\.closest\('details:not\(\[open\]\)'\)\) loadPropBox\(box\)/);
  assert.match(source, /if \(box\.dataset\.loaded\) return;/);
});

test('a climb rung shows its real stake and payout only, and a fun ticket stays apart', () => {
  assert.match(ticketBody, /\$\{money\(info\.stake\)\} → \$\{money\(info\.payout\)\} if it cashes\./);
  assert.match(ticketBody, /Tracked apart from best bets/);
});
