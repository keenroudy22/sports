import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../site/app-kvb.js', import.meta.url), 'utf8');

const setup = () => {
  const sandbox = { window: {}, document: { getElementById: () => null, head: { insertAdjacentHTML: () => {} } } };
  vm.runInNewContext(source, sandbox);
  const isNum = value => typeof value === 'number' && Number.isFinite(value);
  return sandbox.window.KRKvb({
    C: {
      statValue: value => Number(value).toFixed(Number.isInteger(value) ? 0 : 1),
      thresholdResult: (value, line, direction) => direction === 'under' ? value < line ? 'hit' : value > line ? 'miss' : 'push' : value > line ? 'hit' : value < line ? 'miss' : 'push',
    },
    esc: value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
    headshot: (_league, id) => `<i data-player="${id}"></i>`,
    oddsText: odds => Number(odds) > 0 ? `+${odds}` : String(odds).replace('-', '−'),
    whenShort: () => 'Tonight 8:15 PM',
    pctText: value => isNum(value) ? `${Math.round(value * 100)}%` : '–',
    isNum,
    historyChart: (values, labels, line) => `<div class="chart-stub">${values.join(',')}|${labels.join(',')}|${line}</div>`,
    hasValue: row => Boolean(row.value),
  });
};

const row = (id, extra = {}) => ({
  id, gameId: 'NFL-1', athleteId: id, player: `Player ${id}`, league: 'NFL', position: 'WR', stat: 'recYds', isProp: true,
  direction: 'over', line: 49.5, odds: -110, book: 'DraftKings', kickoff: '2026-11-10T01:15:00Z', projection: 61.2,
  chance: .56, needs: .524, edge: 3.6, calibrated: true, thin: false, limited: false, age: { label: '8 min ago' }, src: {}, ...extra,
});
const chartPlayer = (id, stat = 'recYds') => ({ gameId: 'NFL-1', id, side: 'away', rows: [30, 55, 62, 48, 70, 81].map((value, i) => ({ date: `2026-10-${10 + i}`, stats: { [stat]: value } })) });

test('Kook vs. Book puts common props, three comparison numbers and hit-rate charts on Today', () => {
  const api = setup();
  const html = api.home({
    rows: [row('a', { value: true }), row('b', { stat: 'rushYds', position: 'RB', line: 70.5, projection: 76.4, edge: .8 }), row('c', { stat: 'rec', line: 4.5, projection: 5.1, official: true })],
    charts: { players: [chartPlayer('a'), chartPlayer('b', 'rushYds'), chartPlayer('c', 'rec')] },
    games: [{ id: 'NFL-1', away: { abbreviation: 'BUF' }, home: { abbreviation: 'MIN' } }],
  });
  assert.match(html, /Kook vs\. Book[\s\S]*Our number\. Their line\. Your call\./);
  assert.match(html, /Price clears[\s\S]*Book line[\s\S]*Kook’n[\s\S]*Chance gap/);
  assert.match(html, /Official play/);
  assert.match(html, /L5[\s\S]*L10[\s\S]*Season/);
  assert.match(html, /chart-stub/);
  assert.match(html, /Research unless marked Official/);
  assert.match(html, /stat=rec&amp;line=4\.5&amp;direction=over/);
});

test('Kook vs. Book omits fringe, thin, suspect and nonstandard props from the shortlist', () => {
  const api = setup();
  const html = api.home({ rows: [
    row('good'),
    row('thin', { thin: true, edge: 20 }),
    row('fringe', { line: .5, projection: 2.2, edge: 12 }),
    row('td', { stat: 'passTD', line: 1.5, projection: 2.4, edge: 10 }),
    row('held', { src: { roleSuspect: true }, edge: 15 }),
    row('caution', { caution: true, edge: 15 }),
    row('wild', { line: 31.5, projection: 94, edge: .8 }),
  ], charts: { players: [chartPlayer('good')] } });
  assert.match(html, /Player good/);
  for (const hidden of ['Player thin', 'Player fringe', 'Player td', 'Player held', 'Player caution', 'Player wild']) assert.doesNotMatch(html, new RegExp(hidden));
});

test('Kook vs. Book footer keeps the selected sport on the full prop board', () => {
  const api = setup();
  assert.match(api.home({ league: 'NBA', rows: [row('a')] }), /#research\/players\?sport=NBA/);
  assert.match(api.home({ league: 'CBB', rows: [row('a')] }), /#research\/players\?sport=CBB/);
  assert.match(api.home({ rows: [row('a')] }), /#research\/players\?sport=NFL/);
});

test('Today omits the Kook vs. Book panel when no prop qualifies', () => {
  const api = setup();
  assert.equal(api.home(), '');
  assert.equal(api.home({ rows: [row('thin', { thin: true }), row('fringe', { line: .5 })] }), '');
});
