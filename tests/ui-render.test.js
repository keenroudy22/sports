'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('site/app.js', 'utf8');
const moreSource = fs.readFileSync('site/app-more.js', 'utf8');
const gamesSource = fs.readFileSync('site/app-games.js', 'utf8');

test('production JavaScript parses as a standalone browser script', () => {
  assert.doesNotThrow(() => new vm.Script(source, { filename: 'site/app.js' }));
  assert.doesNotThrow(() => new vm.Script(moreSource, { filename: 'site/app-more.js' }));
  assert.doesNotThrow(() => new vm.Script(gamesSource, { filename: 'site/app-games.js' }));
});

test('secondary pages load on demand and stay out of the first-load shell', () => {
  const html = fs.readFileSync('site/index.html', 'utf8');
  assert.doesNotMatch(html, /<script[^>]+app-more\.js/);
  const hash = crypto.createHash('sha256').update(moreSource).digest('hex').slice(0, 12);
  assert.ok(source.includes(`const MORE_ASSET = 'app-more.js?v=sha256-${hash}'`));
  assert.match(source, /script\.src = b\.asset/);
  assert.match(source, /MORE_VIEW_NAMES\.forEach/);
  assert.match(moreSource, /views\.record = async/);
  assert.match(moreSource, /views\.more = async/);
  assert.doesNotMatch(source, /VIEWS\.record = async/);
});

test('Games pages load on demand from their own fingerprinted bundle', () => {
  const html = fs.readFileSync('site/index.html', 'utf8');
  assert.doesNotMatch(html, /<script[^>]+app-games\.js/);
  const hash = crypto.createHash('sha256').update(gamesSource).digest('hex').slice(0, 12);
  assert.ok(source.includes(`const GAMES_ASSET = 'app-games.js?v=sha256-${hash}'`));
  assert.match(source, /GAMES_VIEW_NAMES\.forEach/);
  for (const view of ['games', 'game', 'team']) assert.match(gamesSource, new RegExp(`views\\.${view} = async`));
  assert.match(gamesSource, /views\.gamesLive = gamesLive/);
  assert.doesNotMatch(source, /VIEWS\.games = async route => \{\n    const tab/);
  assert.doesNotMatch(moreSource, /views\.team = async/);
  assert.match(source, /a\[href\^="#game"\], a\[href\^="#team\/"\]/, 'Games links warm the bundle on hover, focus or touch');
  assert.doesNotMatch(source, /far from the book line/);
  assert.doesNotMatch(gamesSource, /far from the book line/);
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
  const games = sandbox.module.exports.ensureGames();
  assert.match(appended.src, /^app-games\.js\?v=sha256-[0-9a-f]{12}$/);
  sandbox.KRGames = ctx => { assert.equal(typeof ctx.liveStamp, 'function'); return { games: () => '<h1>Games</h1>' }; };
  appended.onload();
  assert.equal(typeof (await games).games, 'function');
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
    'not posted yet',
    'Past steps',
    'about 10–15 minutes before X',
    'Covering does not mean winning outright',
  ]) assert.ok(source.includes(wording), wording);
  assert.match(source, /C\.deliveryText\(pick\)/);
  assert.match(source, /C\.quoteStatus\(/);
});

test('suspect player projections and prices have no ranked board row or profile chance', () => {
  const more = fs.readFileSync('site/app-more.js', 'utf8');
  assert.match(source, /filter\(r => !r\.roleSuspect && !r\.priceSuspect\)/);
  assert.doesNotMatch(source, /Lines under review|Projection under review/);
  assert.match(more, /const held = availabilityHeld \|\| projectionReview \|\| Boolean\(heldRow\)/);
  assert.match(more, /UNAVAILABLE/);
});

test('every rendered view preserves the browser-audit page contract', () => {
  const html = fs.readFileSync('site/index.html', 'utf8');
  const audit = fs.readFileSync('tests/browser-audit.mjs', 'utf8');
  assert.match(html, /<main id="view"/);
  assert.match(html, /<noscript>/);
  assert.match(source, /<h1/);
  assert.match(source, /const h1 = view\.querySelector\('h1'\)/, 'the renderer keeps one page-heading focus target');
  assert.match(audit, /\/did not load\/i/, 'a caught route failure must fail the visual audit');
  assert.match(audit, /Judge the pixels a person can actually see/, 'clipped card art must be judged by its visible bounds');
  assert.match(audit, /closest\('\.sr'\)/, 'screen-reader-only headings are not visual overflow');
  assert.match(audit, /\.chip-scroll/, 'intentional chip rails may scroll without hiding page overflow');
});

test('Games restores stored recent MLB and NHL results with an explicit coverage note', () => {
  assert.match(gamesSource, /maybe\('market-lab\.json'\)/);
  assert.match(gamesSource, /Recent team results/);
  assert.match(gamesSource, /Recorded finals only, not a complete season/);
});

test('matchup charts can filter by player or team name', () => {
  assert.match(source, /const nameMatch = pl =>/);
  assert.match(source, /data-input="pq"/);
  assert.match(source, /&& nameMatch\(pl\)/);
  assert.match(source, /History ≠ probability\. \$\{shareLink\('players'\)\}/);
});

test('matchup research is a scan-first prop board with Kookn and paid-tool comparison windows', () => {
  for (const label of ['Book line', 'Kook’n', 'L5', 'L10', 'Season', 'Vs defense']) assert.ok(source.includes(label), label);
  assert.match(source, /class="prop-explorer"/);
  assert.match(source, /class="prop-rate-bar"/);
  assert.match(source, /defenseWords\(teams, String\(opponent\.id\), pl\.pos, key, league, dir\)/);
  assert.match(source, /#research\/trends\?period=1Q&amp;sport=NFL/);
  assert.match(source, /Tap a player for the chart/);
  assert.match(source, /includes\(route\.view\)\) await ensureResearchCss\(\)/);
});

test('game prop tables become scan cards on phones without losing exact stat links', () => {
  assert.match(gamesSource, /data-stat="\$\{esc\(label\)\}"/);
  assert.match(gamesSource, /@media \(max-width:760px\)[\s\S]*\.prop-compare tr \{ display:grid; grid-template-columns:repeat\(3,minmax\(0,1fr\)\)/);
  assert.match(gamesSource, /\.prop-compare thead \{ display:none; \}/);
  assert.match(gamesSource, /content:attr\(data-stat\)/);
  assert.match(gamesSource, /line=\$\{esc\(line\)\}&amp;direction=\$\{esc\(direction\)\}/);
  assert.match(gamesSource, /Priced lines, research leans and highest-minute roles first/);
  assert.match(gamesSource, /class="more-box prop-depth-more"/);
  assert.match(gamesSource, /const featured = players\.slice\(0,5\), depth = players\.slice\(5\)/);
  assert.match(gamesSource, /const featured = ordered\.filter[\s\S]*?\.slice\(0,2\)/);
  assert.match(gamesSource, /More \$\{esc\(pos\)\} players &amp; markets/);
  assert.match(gamesSource, /PRIMARY_POSITION_PROJ/);
});

test('mobile navigation leads with bettor tasks instead of internal research categories', () => {
  assert.match(source, /\['research', 'Props'\]/);
  assert.match(source, /\['record', 'Results'\]/);
  assert.match(source, /Prop finder<\/b><small>Line · Kook’n · L5\/L10/);
  assert.match(source, /First quarter<\/b><small>1Q history & matchups/);
  assert.match(source, /class="research-quick"/);
  assert.match(source, /'Player prop board'/);
  assert.match(source, /'Player stats'/);
  assert.match(source, /'Position vs\. defense'/);
  assert.ok(source.indexOf('${proof}${spotlight}') > -1, 'the current NFL matchup appears before secondary Today sections');
  const research = fs.readFileSync('site/research.css', 'utf8');
  assert.match(research, /\.research-quick \{ display: grid; grid-template-columns: repeat\(5, minmax\(0, 1fr\)\)/);
  assert.match(research, /@media \(max-width: 520px\)[\s\S]*\.research-quick \{ grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
});

test('player result charts and edge sports stay inside phone cards', () => {
  const more = fs.readFileSync('site/app-more.js', 'utf8');
  const research = fs.readFileSync('site/research.css', 'utf8');
  assert.match(more, /Bars and their opponent\/date labels must use the same eight fluid columns/);
  assert.match(more, /\.player-board \.kt-chart \.kt-x \{ width: 100%; grid-auto-columns: minmax\(0,1fr\); gap: 4px; \}/);
  assert.match(more, /\.player-board \.kt-chart \.kt-x span \{ min-width: 0; overflow: visible; overflow-wrap: anywhere; \}/);
  assert.match(research, /@media \(max-width:520px\) \{ \.edge-sports \{ flex-wrap: wrap; overflow: visible; \}/);
  assert.match(more, /const projectionGap = isNum\(projection\) && isNum\(line\) \? projection - line : null/);
  assert.match(more, /Kook’n − book/);
});

test('Today and matchup pages keep the useful decision data ahead of decorative tickets', () => {
  const css = fs.readFileSync('site/app.css', 'utf8');
  assert.match(source, /emptyRail\([^\n]+, 'today-card', true\)/, 'an empty Today rail uses the compact status');
  assert.match(css, /\.decision-empty\.is-compact \{ display: grid;/);
  assert.match(gamesSource, /Official picks in this game/);
  assert.match(gamesSource, /class="matchup-pick-list"/);
  assert.match(gamesSource, /<summary>View original ticket/);
  assert.match(gamesSource, /Kook vs Book · current research/);
  assert.doesNotMatch(gamesSource, /Book lines vs my numbers/);
  assert.match(source, /class="pc-team-abbr"/);
  assert.ok(gamesSource.indexOf("${header}${postedHtml}${linePreview}") > -1, 'the matchup header and compact official rows lead the research stack');
});
