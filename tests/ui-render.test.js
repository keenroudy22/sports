'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');

test('production JavaScript parses as a standalone browser script', () => {
  assert.doesNotThrow(() => new vm.Script(source, { filename: 'site/app.js' }));
  assert.doesNotThrow(() => new vm.Script(moreSource, { filename: 'site/app-more.js' }));
});

test('secondary pages load on demand and stay out of the first-load shell', () => {
  const html = fs.readFileSync('site/index.html', 'utf8');
  assert.doesNotMatch(html, /<script[^>]+app-more\.js/);
  assert.match(source, /script\.src = 'app-more\.js\?v=2'/);
  assert.match(source, /MORE_VIEW_NAMES\.forEach/);
  assert.match(moreSource, /views\.record = async/);
  assert.match(moreSource, /views\.team = async/);
  assert.match(moreSource, /views\.more = async/);
  assert.doesNotMatch(source, /VIEWS\.record = async/);
});

test('Today extras rerender through the exported route parser', () => {
  assert.match(source, /C\.parseRoute\(location\.hash\)\.view === 'today'/);
  assert.doesNotMatch(source, /C\.routePath\(/);
  assert.match(source, /Date\.now\(\) - todayExtrasAt < DATA_TTL/);
  assert.match(source, /todayExtrasAt = Date\.now\(\)/);
});

test('a temporary record payload miss keeps the last complete record in memory', () => {
  assert.match(source, /let previousEvery = null/);
  assert.match(source, /if \(!previousEvery\) return today\.picks \|\| \[\]/);
  assert.match(source, /previousEvery = \[\.\.\.byId\.values\(\)\]/);
});

test('replacement UI keeps the owner-mandated wording and shared labels', () => {
  for (const wording of [
    'being checked · not posted yet',
    'Past steps',
    'about 10–15 minutes before X',
    'Covering does not mean winning outright',
  ]) assert.ok(source.includes(wording), wording);
  assert.match(source, /C\.deliveryText\(pick\)/);
  assert.match(source, /C\.quoteStatus\(/);
});

test('every rendered view preserves the browser-audit page contract', () => {
  const html = fs.readFileSync('site/index.html', 'utf8');
  assert.match(html, /<main id="view"/);
  assert.match(html, /<noscript>/);
  assert.match(source, /<h1/);
  assert.match(source, /const h1 = view\.querySelector\('h1'\)/, 'the renderer keeps one page-heading focus target');
});

test('Games restores stored recent MLB and NHL results with an explicit coverage note', () => {
  assert.match(source, /maybe\('market-lab\.json'\)/);
  assert.match(source, /Recent team results/);
  assert.match(source, /Recorded finals only, not a complete season/);
});

test('matchup charts can filter by player or team name', () => {
  assert.match(source, /const nameMatch = pl =>/);
  assert.match(source, /data-input="pq"/);
  assert.match(source, /&& nameMatch\(pl\)/);
  assert.match(source, /History is not a probability\. \$\{shareLink\('players'\)\}/);
});
