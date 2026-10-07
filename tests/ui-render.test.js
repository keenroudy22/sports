'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
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
  const hash = crypto.createHash('sha256').update(moreSource).digest('hex').slice(0, 12);
  assert.ok(source.includes(`const MORE_ASSET = 'app-more.js?v=sha256-${hash}'`));
  assert.match(source, /script\.src = MORE_ASSET/);
  assert.match(source, /MORE_VIEW_NAMES\.forEach/);
  assert.match(moreSource, /views\.record = async/);
  assert.match(moreSource, /views\.team = async/);
  assert.match(moreSource, /views\.more = async/);
  assert.doesNotMatch(source, /VIEWS\.record = async/);
});

test('a lazy bundle factory error rejects and allows a clean retry', async () => {
  let appended = null;
  const sandbox = {
    module: { exports: {} }, exports: {}, KRCore: require('../site/core.js'),
    KRLive: require('../site/live.js'), KRPersonal: require('../site/personal.js'),
    document: {
      querySelector: () => null,
      createElement: () => ({}),
      head: { appendChild: script => { appended = script; } },
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    console, URL, URLSearchParams, Intl, Date, Math, Map, Set, Promise,
    AbortController, TextEncoder, TextDecoder, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  sandbox.globalThis = sandbox; sandbox.self = sandbox; sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox, { filename: 'site/app.js' });
  const first = sandbox.module.exports.ensureMore();
  assert.ok(appended);
  assert.match(appended.src, /^app-more\.js\?v=sha256-[0-9a-f]{12}$/);
  sandbox.KRMore = () => { throw new Error('factory exploded'); };
  appended.onload();
  await assert.rejects(first, /factory exploded/);
  sandbox.KRMore = () => ({ record: () => '<h1>Record</h1>' });
  const retried = await sandbox.module.exports.ensureMore();
  assert.equal(typeof retried.record, 'function');
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
  const audit = fs.readFileSync('tests/browser-audit.mjs', 'utf8');
  assert.match(html, /<main id="view"/);
  assert.match(html, /<noscript>/);
  assert.match(source, /<h1/);
  assert.match(source, /const h1 = view\.querySelector\('h1'\)/, 'the renderer keeps one page-heading focus target');
  assert.match(audit, /\/did not load\/i/, 'a caught route failure must fail the visual audit');
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
