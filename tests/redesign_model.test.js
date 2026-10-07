/* Unit tests for the redesign's pure model functions. Run: node --test redesign/tests/*.test.js
   Resolves the shared site files whether this folder sits at redesign/tests or tests/ after the port. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const find = (...candidates) => candidates.map(p => path.resolve(__dirname, p)).find(p => fs.existsSync(p));
globalThis.KRCore = require(find('../site/core.js', '../../site/core.js'));
const { model: M } = require(find('../site/app.js', '../redesign/site/app.js'));

test('break-even matches the price', () => {
  assert.equal(Math.round(M.breakEven(-110) * 1000), 524);
  assert.equal(Math.round(M.breakEven(100) * 1000), 500);
  assert.equal(Math.round(M.breakEven(108) * 1000), 481);
  assert.equal(M.breakEven(0), null);
  assert.equal(M.breakEven('x'), null);
});

test('fair price is the American odds of our chance', () => {
  assert.equal(M.fairAmerican(0.54), -117);
  assert.equal(M.fairAmerican(0.554), -124);
  assert.equal(M.fairAmerican(0.4), 150);
  assert.equal(M.fairAmerican(0), null);
  assert.equal(M.fairAmerican(1), null);
});

test('edge is chance minus break-even in points', () => {
  assert.equal(M.edgePoints(0.537, 0.505), 3.2);
  assert.equal(M.edgePoints(0.5, 0.524), -2.4);
  assert.equal(M.edgePoints(null, 0.5), null);
});

test('price age labels', () => {
  const now = Date.parse('2026-10-06T20:00:00Z');
  const kickoff = '2026-10-07T00:00:00Z';
  assert.equal(M.quoteAge('2026-10-06T19:30:00Z', kickoff, now, { odds: -110, state: 'open' }).kind, 'fresh');
  assert.equal(M.quoteAge('2026-10-06T17:30:00Z', kickoff, now, { odds: -110, state: 'open' }).kind, 'aging');
  assert.equal(M.quoteAge('2026-10-06T14:00:00Z', kickoff, now, { odds: -110, state: 'open' }).kind, 'stale');
  assert.equal(M.quoteAge('2026-10-06T19:30:00Z', '2026-10-06T19:00:00Z', now, { odds: -110 }).kind, 'started');
  assert.equal(M.quoteAge('2026-10-06T19:30:00Z', kickoff, now, { odds: null }).kind, 'unpriced');
  assert.equal(M.quoteAge('2026-10-06T19:30:00Z', kickoff, now, { odds: -110, expiresAt: '2026-10-06T19:45:00Z' }).kind, 'stale');
});

test('book names: unavailable hidden, rebrands applied', () => {
  assert.equal(M.bookLabel('Book unavailable'), null);
  assert.equal(M.bookLabel(''), null);
  assert.equal(M.bookLabel('hardrockbet'), 'Hard Rock Bet');
  assert.equal(M.bookLabel('ESPN BET'), 'theScore Bet');
  assert.equal(M.bookLabel('DraftKings'), 'DraftKings');
});

test('game totals are never labeled team props', () => {
  assert.equal(M.marketLabel({ kind: 'gamePicks', marketType: 'total', direction: 'over', displayTitle: 'Iowa at Washington over 41.5' }), 'Game total');
  assert.equal(M.marketLabel({ market: 'total points', gameMarket: true }), 'Game total');
  assert.equal(M.marketLabel({ market: 'point spread', gameMarket: true }), 'Spread');
  assert.equal(M.marketLabel({ athleteId: '1', market: 'recYds' }), 'Player prop · receiving yards');
  assert.equal(M.marketLabel({ parlayType: 'ladder' }), '80/20 Climb');
  assert.equal(M.marketLabel({ kind: 'parlays', legs: [{}, {}] }), 'Fun ticket');
});

test('why lines never use counterpoints or raw-model sentences', () => {
  const pick = { why: 'Prop lean: our projection is 68.2 against 49.5. The over reads 53.7% after adjustment from the raw 65.9%; 50.5% is needed at -102. Last 10 games: 5 of 10 over 49.5. Role: 1st of 1 NMSU WRs by projected targets, 7.3 a game.',
    risk: "The opponent's positional allowance points against this side. It covers the whole position group. An estimated chance, not a guarantee. Confidence 2 of 10." };
  const why = M.whyLines(pick);
  assert.deepEqual(why, ['Role: 7.3 projected targets a game.'], 'a hit count is history and one-player groups have no rank');
  assert.equal(M.historyLine(pick), 'Last 10 games: 5 of 10 over 49.5.');
  assert.ok(why.every(s => !/raw|against this side/i.test(s)));
  assert.equal(M.watchLine(pick), "The opponent's positional allowance points against this side.");
});

test('how-we-got-it explains the shrink without hiding it', () => {
  const lines = M.howWeGotIt({ projection: 68.2, line: 49.5, odds: -102, probabilityAtPublication: { rawChance: 0.659, chance: 0.537, calibration: 0.23, calibrationN: 398, breakEven: 0.505 } });
  assert.match(lines.join(' '), /65.9%|66%/);
  assert.match(lines.join(' '), /54%/);
  assert.match(lines.join(' '), /398 graded lines/);
  assert.match(lines.join(' '), /cut it down hard/);
});

test('pick view model: open best bet shows our chance on the stub, results show tickets', () => {
  const base = { id: 'x', kind: 'props', athleteId: '1', market: 'recYds', displayTitle: 'A B OVER 49.5 receiving yards', odds: -102, book: 'DraftKings',
    kickoff: '2099-01-01T00:00:00Z', status: 'active', probabilityAtPublication: { chance: 0.537, breakEven: 0.505, edgePoints: 3.2 } };
  const open = M.pickVM(base, Date.parse('2026-10-06T00:00:00Z'));
  assert.equal(open.title, 'A B over 49.5 receiving yards');
  assert.equal(open.stub.big, '54%');
  assert.equal(open.fair, -116);
  assert.equal(M.pickVM({ ...base, result: 'win' }).stub.cls, 'hit');
  assert.equal(M.pickVM({ ...base, result: 'loss' }).stub.cls, 'miss');
  assert.equal(M.pickVM({ ...base, result: 'push' }).stub.cls, 'push');
});

test('a play whose posted price window passed still stands, in plain words', () => {
  const base = { id: 'y', kind: 'gamePicks', marketType: 'total', direction: 'over', displayTitle: 'A at B over 41.5', odds: -110, book: 'DraftKings',
    kickoff: '2099-01-01T00:00:00Z', expiresAt: '2026-10-01T00:00:00Z', status: 'active', probabilityAtPublication: { chance: 0.55, breakEven: 0.524 } };
  const vm = M.pickVM(base, Date.parse('2026-10-06T00:00:00Z'));
  assert.equal(vm.standing, true);
  assert.equal(vm.status, 'Posted price may be gone');
  assert.match(vm.statusNote, /graded at -110 \(DraftKings\), the price we posted/);
  assert.equal(vm.mode, 'expired');
  assert.equal(vm.stub.cls, 'closed', 'an old price never gets the green open stub');
  assert.equal(vm.stub.small, 'at posted price');
  const noChance = M.pickVM({ ...base, probabilityAtPublication: null }, Date.parse('2026-10-06T00:00:00Z'));
  assert.equal(noChance.stub.big, '-110');
  assert.equal(noChance.stub.small, 'posted price');
  assert.ok(![vm.status, vm.statusNote, vm.stub.small].some(t => /expired/i.test(t)));
});

test('a play the desk closed, pulled or withdrew never reads as open', () => {
  const now = Date.parse('2026-10-06T00:00:00Z');
  const base = { id: 'z', kind: 'gamePicks', marketType: 'total', direction: 'under', displayTitle: 'A at B under 56.5', line: 56.5, odds: -110, book: 'FanDuel',
    kickoff: '2099-01-01T00:00:00Z', status: 'active', probabilityAtPublication: { chance: 0.55, breakEven: 0.524 } };
  const moved = M.pickVM({ ...base, entryNote: 'Closed to new entries at 11:45 AM ET: total moved 2 against us.' }, now);
  assert.equal(moved.mode, 'closed');
  assert.equal(moved.status, 'Off the card');
  assert.equal(moved.stub.cls, 'closed');
  assert.match(moved.statusNote, /Closed to new entries at 11:45 AM ET.*still graded at 56.5 -110 \(FanDuel\)/);
  assert.doesNotMatch(moved.statusNote, /check your book/i);
  const pulled = M.pickVM({ ...base, entryNote: 'Pulled over news before its post went out.' }, now);
  assert.equal(pulled.status, 'Pulled before posting');
  assert.equal(pulled.stub.cls, 'closed');
  const gone = M.pickVM({ ...base, status: 'withdrawn' }, now);
  assert.equal(gone.mode, 'closed');
  assert.match(gone.statusNote, /^Withdrawn before kickoff/);
});

test('fun tickets: string legs, estimated prices and the posted book name', () => {
  const vm = M.pickVM({ id: 'f', kind: 'parlays', parlayType: 'longshot', odds: 1250, book: 'ESPN BET', priceEstimated: true, kickoff: '2099-01-01T00:00:00Z', status: 'active',
    legs: ['Lions ML', { title: 'Bills OVER 47.5' }, ''] }, Date.parse('2026-10-06T00:00:00Z'));
  assert.deepEqual(vm.legs, ['Lions ML', 'Bills over 47.5']);
  assert.equal(vm.estimated, true);
  assert.equal(vm.lotto, true);
  assert.equal(vm.book, 'ESPN BET (now theScore Bet)');
  assert.equal(M.postedBook('DraftKings'), 'DraftKings');
});

test('a best bet badges only its own market and side on the board', () => {
  const pick = { gameId: 'NFL-1', athleteId: '9', market: 'rec', direction: 'over' };
  assert.equal(M.officialKey(pick), M.officialKey({ gameId: 'NFL-1', athleteId: '9', market: 'receptions', direction: 'OVER' }));
  assert.notEqual(M.officialKey(pick), M.officialKey({ gameId: 'NFL-1', athleteId: '9', market: 'receiving yards', direction: 'over' }));
  assert.equal(M.officialKey({ gameId: 'CFB-2', marketType: 'spread', direction: 'home' }), M.officialKey({ gameId: 'CFB-2', market: 'point spread', side: 'home' }));
  assert.notEqual(M.officialKey({ gameId: 'CFB-2', marketType: 'total', direction: 'under' }), M.officialKey({ gameId: 'CFB-2', market: 'point spread', side: 'home' }));
});

test('research rows: best price only compares the same line, Hard Rock excluded', () => {
  const row = { id: 'r', title: 'P over 224.5 passing yards', athleteId: '9', market: 'passing yards', line: 224.5, odds: -114, book: 'FanDuel', state: 'open',
    kickoff: '2099-01-01T00:00:00Z', observedAt: new Date().toISOString(),
    books: [{ book: 'FanDuel', line: 224.5, odds: -114 }, { book: 'ESPN BET', line: 224.5, odds: -120 }, { book: 'DraftKings', line: 199.5, odds: -207 }, { book: 'hardrockbet', line: 224.5, odds: 105 }],
    grade: { chance: 0.56, needs: 0.533, edge: 2.7, tier: 'lean', calibrated: true } };
  const vm = M.lineVM(row);
  assert.equal(vm.bestOdds, -114);
  assert.equal(vm.bestBook, 'FanDuel');
  assert.equal(vm.booksCount, 2);
  assert.equal(vm.otherLines.length, 1);
  assert.equal(vm.fair, -127);
  assert.ok(M.hasValue(vm));
  assert.ok(!M.hasValue({ ...vm, thin: true }));
});

test('collapse keeps the strongest edge per player, stat and side', () => {
  const rows = [
    { gameId: 'g', athleteId: '1', stat: 'recYds', isProp: true, direction: 'over', edge: 1.5, line: 40 },
    { gameId: 'g', athleteId: '1', stat: 'recYds', isProp: true, direction: 'over', edge: 3.1, line: 42.5 },
    { gameId: 'g', athleteId: '1', stat: 'recYds', isProp: true, direction: 'under', edge: -1, line: 40 },
  ];
  const out = M.collapse(rows);
  assert.equal(out.length, 2);
  const over = out.find(r => r.direction === 'over');
  assert.equal(over.edge, 3.1);
  assert.equal(over.alternates, 1);
});

test('heavy favorites are flagged and trends read as counts, never a bare 100%', () => {
  assert.equal(M.heavyFavorite(-900), true);
  assert.equal(M.heavyFavorite(-250), false);
  assert.equal(M.trendText({ hits: 4, games: 4, odds: -900 }), '4 of 4 · price needs 90%');
  assert.equal(M.trendText({ hits: 3, games: 4, odds: null }), '3 of 4 · no price captured');
});

test('games rank by gap percentile and demote FCS or missing markets', () => {
  const g = p => ({ market: {}, v2: {}, marketRead: { ourGap: { margin: { percentile: p }, total: { percentile: 10 } } } });
  assert.equal(M.gapScore(g(91)), 91);
  assert.equal(M.gapScore({ ...g(91), fcs: true }), -1);
  assert.equal(M.gapScore({ ...g(91), market: null }), -1);
});

test('cumulative units end at the captured-price total and exclude promo credits', () => {
  const picks = [
    { id: 'a', odds: -110, result: 'win', settledAt: '2026-09-01' },
    { id: 'b', odds: 100, result: 'loss', settledAt: '2026-09-02', earlyExit: true },
    { id: 'c', odds: -110, result: 'win', priceAssumed: true, settledAt: '2026-09-03' },
    { id: 'd', kind: 'parlays', legs: [{}], odds: 500, result: 'win', settledAt: '2026-09-04' },
  ];
  const pts = M.cumulativeUnits(picks, globalThis.KRCore.unitsFor);
  assert.equal(pts.length, 2);
  assert.equal(pts.at(-1).units, Math.round((100 / 110 - 1) * 100) / 100);
});

test('closing-line summary counts beat, tied and lost', () => {
  const s = M.clvSummary([{ clv: 1 }, { clv: 0 }, { clv: -0.5 }, { clv: null }]);
  assert.deepEqual([s.measured, s.beat, s.tied, s.lost], [3, 1, 1, 1]);
});

test('every legacy link lands on its new screen', () => {
  const cases = {
    '': 'today', '#today': 'today', '#sports': 'today', '#home': 'today', '#overview': 'today', '#digest': 'today',
    '#pick/CFB-2026-W6-x': 'pick', '#board': 'research', '#board/props': 'research', '#board/favorites': 'research', '#lines': 'research',
    '#props': 'research', '#trends': 'research', '#trends/CFB-1': 'research', '#stats': 'research', '#stats/defense': 'research',
    '#charts': 'research', '#players': 'research', '#defense': 'research', '#games': 'games', '#scores': 'games', '#scores/NHL': 'games',
    '#sport/NBA': 'games', '#game/CFB-401871090': 'game', '#player/CFB/5150277': 'player', '#team/NFL/12': 'team', '#record': 'record',
    '#record/trials': 'record', '#results': 'record', '#model': 'record', '#more': 'more', '#tools': 'more', '#ticket': 'ticket',
    '#parlays': 'ticket', '#saved': 'saved', '#start': 'start', '#arbs': 'arbs', '#lab': 'lab', '#schedule': 'schedule',
    '#feedback': 'feedback', '#research': 'research', '#nonsense': 'today',
  };
  for (const [hash, view] of Object.entries(cases)) assert.equal(M.resolve(hash).view, view, hash);
  assert.equal(M.resolve('#board/props').type, 'props');
  assert.equal(M.resolve('#board').type, 'games');
  assert.equal(M.resolve('#board/favorites').sort, 'edge');
  assert.equal(M.resolve('#trends').mode, 'trends');
  assert.equal(M.resolve('#stats/defense').sub, 'defense');
  assert.equal(M.resolve('#record/trials').tab, 'trials');
  assert.equal(M.resolve('#model').tab, 'model');
  assert.equal(M.resolve('#pick/CFB-2026-W6-a/b').id, 'CFB-2026-W6-a/b');
});

test('legacy links rewrite to the new address; deep links never change', () => {
  assert.equal(M.canonical(M.resolve('#board/props')), '#research/lines?type=props');
  assert.equal(M.canonical(M.resolve('#trends')), '#research/trends');
  assert.equal(M.canonical(M.resolve('#scores/NHL')), '#games/live?sport=NHL');
  assert.equal(M.canonical(M.resolve('#model')), '#record/model');
  assert.equal(M.canonical(M.resolve('#pick/x')), null);
  assert.equal(M.canonical(M.resolve('#game/CFB-1')), null);
  assert.equal(M.canonical(M.resolve('#player/NFL/1')), null);
  assert.equal(M.resolve('#games/live?sport=NHL').league, 'NHL');
});

test('no hype words in the new UI copy', () => {
  const source = fs.readFileSync(find('../site/app.js', '../redesign/site/app.js'), 'utf8');
  assert.ok(!/\block\b|guarantee[sd]? (?:win|profit)|can't lose|risk-free|highest confidence/i.test(source));
});

test('css keeps text at readable sizes', () => {
  const css = fs.readFileSync(find('../site/app.css', '../redesign/site/app.css'), 'utf8');
  const sizes = [...css.matchAll(/font(?:-size)?:\s*(?:\d+\s+)?(\d+)px/g)].map(m => Number(m[1]));
  const tooSmall = sizes.filter(px => px < 12);
  assert.ok(tooSmall.every(px => px >= 10), `found ${tooSmall}`);
  assert.ok(sizes.filter(px => px < 12).length <= 2, 'only the decorative team marks may go below 12px');
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /--burnt-text/);
});
